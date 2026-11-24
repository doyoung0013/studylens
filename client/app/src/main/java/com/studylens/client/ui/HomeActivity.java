package com.studylens.client.ui;

import androidx.appcompat.app.AppCompatActivity;

import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.widget.*;

import com.studylens.client.R;
import com.studylens.client.api.ApiClient;
import com.studylens.client.api.ApiService;
import com.studylens.client.model.CurrentStatus;
import com.studylens.client.model.DailyStat;
import com.studylens.client.model.SessionSummary;
import com.studylens.client.util.Prefs;
import com.studylens.client.util.TimeFormat;

import java.time.LocalDate;
import java.time.YearMonth;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class HomeActivity extends AppCompatActivity {

    private static final int GOAL_MINUTES = 60;
    private static final long LIVE_REFRESH_MS = 30_000;

    LinearLayout calendarGrid;
    Button btnGallery;
    ApiService api;

    TextView tvMonthTitle, tvMonthBadge, tvCardTitle;
    TextView tvTodayMinutes, tvFocusInfo;
    ProgressBar progressToday;

    // 실시간 상태
    View liveDot;
    TextView tvLiveStatus, tvLiveDetail;
    final Handler handler = new Handler(Looper.getMainLooper());
    final Runnable liveRefresher = new Runnable() {
        @Override
        public void run() {
            loadCurrentStatus();
            handler.postDelayed(this, LIVE_REFRESH_MS);
        }
    };

    // 달력 상태
    YearMonth shownMonth = YearMonth.now();
    LocalDate selectedDate = LocalDate.now();
    TextView selectedDateView = null;
    final Map<LocalDate, DailyStat> statsByDate = new HashMap<>();
    final Map<LocalDate, TextView> dayViews = new HashMap<>();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_home);

        calendarGrid = findViewById(R.id.calendarGrid);
        btnGallery = findViewById(R.id.btnGallery);
        tvMonthTitle = findViewById(R.id.tvMonthTitle);
        tvMonthBadge = findViewById(R.id.tvMonthBadge);
        tvCardTitle = findViewById(R.id.tvCardTitle);
        tvTodayMinutes = findViewById(R.id.tvTodayMinutes);
        tvFocusInfo = findViewById(R.id.tvFocusInfo);
        progressToday = findViewById(R.id.progressToday);
        progressToday.setMax(GOAL_MINUTES);

        liveDot = findViewById(R.id.liveDot);
        tvLiveStatus = findViewById(R.id.tvLiveStatus);
        tvLiveDetail = findViewById(R.id.tvLiveDetail);

        api = ApiClient.getClient(this).create(ApiService.class);

        findViewById(R.id.btnPrevMonth).setOnClickListener(v -> changeMonth(-1));
        findViewById(R.id.btnNextMonth).setOnClickListener(v -> changeMonth(1));

        btnGallery.setOnClickListener(v -> {
            Intent i = new Intent(this, StudyGalleryActivity.class);
            i.putExtra(StudyGalleryActivity.EXTRA_DATE, selectedDate.toString());
            startActivity(i);
        });

        buildCalendar();
        loadMonthStats();
    }

    @Override
    protected void onResume() {
        super.onResume();
        handler.post(liveRefresher);
    }

    @Override
    protected void onPause() {
        super.onPause();
        handler.removeCallbacks(liveRefresher);
    }

    // ==============================================================
    // 실시간 상태
    // ==============================================================
    private void loadCurrentStatus() {
        api.getCurrent().enqueue(new Callback<CurrentStatus>() {
            @Override
            public void onResponse(Call<CurrentStatus> call, Response<CurrentStatus> res) {
                if (res.code() == 401) {
                    goToLogin();
                    return;
                }
                if (!res.isSuccessful() || res.body() == null) return;
                renderLiveStatus(res.body());
            }

            @Override
            public void onFailure(Call<CurrentStatus> call, Throwable t) {
                tvLiveStatus.setText("서버에 연결할 수 없어요");
                tvLiveDetail.setText("");
                liveDot.setBackgroundResource(R.drawable.bg_live_idle);
            }
        });
    }

    private void renderLiveStatus(CurrentStatus status) {
        SessionSummary s = status.session;
        if (status.studying && s != null) {
            int minutes = s.elapsedSeconds / 60;
            if (s.isDistracted) {
                liveDot.setBackgroundResource(R.drawable.bg_live_distracted);
                tvLiveStatus.setText("딴짓 감지 중 · " + minutes + "분째");
            } else {
                liveDot.setBackgroundResource(R.drawable.bg_live_on);
                tvLiveStatus.setText("지금 공부 중 · " + minutes + "분째");
            }
            tvLiveDetail.setText("이번 세션 순공부 " + TimeFormat.minutes(s.focusSeconds)
                    + " · 집중도 " + TimeFormat.rate(s.focusRate));
        } else {
            liveDot.setBackgroundResource(R.drawable.bg_live_idle);
            tvLiveStatus.setText("지금은 공부 중이 아니에요");
            tvLiveDetail.setText("책을 펴고 앉으면 자동으로 기록이 시작돼요");
        }

        // 오늘 통계도 함께 갱신 (진행 중 세션 포함)
        if (status.today != null) {
            statsByDate.put(LocalDate.now(), status.today);
            refreshDayStyle(LocalDate.now());
            if (selectedDate.equals(LocalDate.now())) updateCard();
        }
    }

    // ==============================================================
    // 달력
    // ==============================================================
    private void changeMonth(int delta) {
        YearMonth next = shownMonth.plusMonths(delta);
        if (next.isAfter(YearMonth.now())) return;  // 미래 달은 표시하지 않음
        shownMonth = next;
        selectedDate = shownMonth.equals(YearMonth.now()) ? LocalDate.now() : shownMonth.atDay(1);
        buildCalendar();
        loadMonthStats();
    }

    /** shownMonth 기준으로 달력 칸을 생성한다. (일요일 시작) */
    private void buildCalendar() {
        tvMonthTitle.setText(shownMonth.getMonthValue() + "월 학습 현황");
        tvMonthBadge.setText(shownMonth.format(DateTimeFormatter.ofPattern("yyyy.MM")));

        calendarGrid.removeAllViews();
        dayViews.clear();
        selectedDateView = null;

        int firstOffset = shownMonth.atDay(1).getDayOfWeek().getValue() % 7; // 일=0 ... 토=6
        int length = shownMonth.lengthOfMonth();
        int cells = (int) Math.ceil((firstOffset + length) / 7.0) * 7;
        int size = dp(36);

        LinearLayout row = null;
        for (int i = 0; i < cells; i++) {
            if (i % 7 == 0) {
                row = new LinearLayout(this);
                row.setOrientation(LinearLayout.HORIZONTAL);
                row.setPadding(0, dp(2), 0, dp(2));
                calendarGrid.addView(row, new LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));
            }

            FrameLayout cell = new FrameLayout(this);
            row.addView(cell, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

            int dayNum = i - firstOffset + 1;
            if (dayNum < 1 || dayNum > length) continue;

            LocalDate date = shownMonth.atDay(dayNum);
            TextView tv = new TextView(this);
            tv.setText(String.valueOf(dayNum));
            tv.setGravity(Gravity.CENTER);
            tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
            FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(size, size);
            lp.gravity = Gravity.CENTER;
            cell.addView(tv, lp);

            dayViews.put(date, tv);
            if (date.isAfter(LocalDate.now())) {
                tv.setTextColor(Color.parseColor("#D1D5DB"));
            } else {
                tv.setOnClickListener(v -> selectDate(date));
            }
            refreshDayStyle(date);
        }

        selectDate(selectedDate);
    }

    private void selectDate(LocalDate date) {
        TextView newView = dayViews.get(date);
        if (newView == null) return;

        LocalDate prev = selectedDate;
        selectedDate = date;
        if (selectedDateView != null) refreshDayStyle(prev);
        selectedDateView = newView;
        refreshDayStyle(date);
        updateCard();
    }

    /** 날짜 칸 스타일: 선택됨 > 공부한 날 > 기본 */
    private void refreshDayStyle(LocalDate date) {
        TextView tv = dayViews.get(date);
        if (tv == null) return;
        if (date.isAfter(LocalDate.now())) return;

        DailyStat stat = statsByDate.get(date);
        if (date.equals(selectedDate)) {
            tv.setBackgroundResource(R.drawable.bg_day_selected);
            tv.setTextColor(Color.WHITE);
        } else if (stat != null && stat.totalSeconds >= 60) {
            tv.setBackgroundResource(R.drawable.bg_day_active);
            tv.setTextColor(Color.parseColor("#15803d"));
        } else {
            tv.setBackground(null);
            tv.setTextColor(Color.parseColor("#4B5563"));
        }
    }

    // ==============================================================
    // 통계
    // ==============================================================
    private void loadMonthStats() {
        LocalDate start = shownMonth.atDay(1);
        LocalDate end = shownMonth.atEndOfMonth();
        if (end.isAfter(LocalDate.now())) end = LocalDate.now();
        final YearMonth requested = shownMonth;

        api.getStatsRange(start.toString(), end.toString()).enqueue(new Callback<List<DailyStat>>() {
            @Override
            public void onResponse(Call<List<DailyStat>> call, Response<List<DailyStat>> res) {
                if (res.code() == 401) {
                    goToLogin();
                    return;
                }
                if (!res.isSuccessful() || res.body() == null) {
                    Log.e("API", "통계 응답 실패: " + res.code());
                    return;
                }
                if (!requested.equals(shownMonth)) return; // 그 사이 달이 바뀜

                for (DailyStat stat : res.body()) {
                    LocalDate d = LocalDate.parse(stat.date);
                    statsByDate.put(d, stat);
                    refreshDayStyle(d);
                }
                updateCard();
            }

            @Override
            public void onFailure(Call<List<DailyStat>> call, Throwable t) {
                Log.e("API", "통계 로드 실패", t);
                Toast.makeText(HomeActivity.this, "통계를 불러오지 못했어요", Toast.LENGTH_SHORT).show();
            }
        });
    }

    /** 선택된 날짜의 순공부 시간 / 집중도를 카드에 표시 */
    private void updateCard() {
        boolean isToday = selectedDate.equals(LocalDate.now());
        tvCardTitle.setText(isToday ? "오늘의 학습"
                : selectedDate.getMonthValue() + "월 " + selectedDate.getDayOfMonth() + "일 학습");

        DailyStat stat = statsByDate.get(selectedDate);
        int focusMin = stat != null ? stat.focusSeconds / 60 : 0;

        tvTodayMinutes.setText(String.valueOf(focusMin));
        progressToday.setProgress(Math.min(focusMin, GOAL_MINUTES));

        if (stat == null || stat.totalSeconds == 0) {
            tvFocusInfo.setText("공부 기록이 없어요");
        } else {
            tvFocusInfo.setText("전체 " + TimeFormat.minutes(stat.totalSeconds)
                    + " · 딴짓 " + TimeFormat.minutes(stat.distractedSeconds)
                    + " · 집중도 " + TimeFormat.rate(stat.focusRate));
        }

        btnGallery.setText(isToday ? "오늘의 공부 모습 보러가기"
                : selectedDate.getDayOfMonth() + "일 공부 모습 보러가기");
    }

    // ==============================================================
    private void goToLogin() {
        Prefs.clear(this);
        Intent i = new Intent(this, LoginActivity.class);
        i.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        startActivity(i);
        finish();
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
