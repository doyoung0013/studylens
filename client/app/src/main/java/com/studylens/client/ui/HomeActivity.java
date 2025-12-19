package com.studylens.client.ui;

import androidx.appcompat.app.AppCompatActivity;

import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.*;

import com.studylens.client.R;
import com.studylens.client.api.ApiClient;
import com.studylens.client.api.ApiService;
import com.studylens.client.model.DailyStat;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class HomeActivity extends AppCompatActivity {

    LinearLayout calendarGrid;
    Button btnGallery;
    ApiService api;

    // ✅ 오늘의 학습 UI
    TextView tvTodayMinutes;
    ProgressBar progressToday;

    // 현재 선택된 날짜
    TextView selectedDateView = null;
    int selectedDay = 1;

    // 서버에서 받아온 공부한 날짜
    List<Integer> activeDays = new ArrayList<>();

    // 날짜별 공부 시간 (분)
    Map<Integer, Integer> dailyMinutesMap = new HashMap<>();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_home);

        calendarGrid = findViewById(R.id.calendarGrid);
        btnGallery = findViewById(R.id.btnGallery);

        // ✅ 오늘의 학습 카드
        tvTodayMinutes = findViewById(R.id.tvTodayMinutes);
        progressToday = findViewById(R.id.progressToday);

        api = ApiClient.getClient(getApplicationContext()).create(ApiService.class);

        setupCalendarEvents();
        loadStats();

        btnGallery.setOnClickListener(v ->
                startActivity(new Intent(this, StudyGalleryActivity.class))
        );
    }

    /**
     * 📅 캘린더 클릭 이벤트 연결
     */
    private void setupCalendarEvents() {
        int rowCount = calendarGrid.getChildCount();

        for (int i = 0; i < rowCount; i++) {
            View child = calendarGrid.getChildAt(i);
            if (!(child instanceof LinearLayout)) continue;

            LinearLayout weekRow = (LinearLayout) child;
            int dayCount = weekRow.getChildCount();

            for (int j = 0; j < dayCount; j++) {
                View dayContainer = weekRow.getChildAt(j);
                if (!(dayContainer instanceof FrameLayout)) continue;

                FrameLayout frame = (FrameLayout) dayContainer;
                if (frame.getChildCount() == 0) continue;

                View v = frame.getChildAt(0);
                if (!(v instanceof TextView)) continue;

                TextView dayTextView = (TextView) v;
                String dayText = dayTextView.getText().toString();
                if (dayText.isEmpty()) continue;

                int dayNum = Integer.parseInt(dayText);

                dayTextView.setOnClickListener(view ->
                        handleDateClick(dayTextView, dayNum)
                );
            }
        }
    }

    /**
     * 📅 날짜 클릭 시
     */
    private void handleDateClick(TextView newView, int newDay) {

        if (selectedDateView == newView) return;

        if (selectedDateView != null) {
            int prevDay = Integer.parseInt(selectedDateView.getText().toString());

            if (activeDays.contains(prevDay)) {
                selectedDateView.setBackgroundResource(R.drawable.bg_day_active);
                selectedDateView.setTextColor(Color.parseColor("#15803d"));
            } else {
                selectedDateView.setBackground(null);
                selectedDateView.setTextColor(Color.parseColor("#4B5563"));
            }
        }

        newView.setBackgroundResource(R.drawable.bg_day_selected);
        newView.setTextColor(Color.WHITE);

        selectedDateView = newView;
        selectedDay = newDay;

        updateTodayCard(selectedDay);
    }

    /**
     * 🌐 서버에서 통계 로드
     */
    private void loadStats() {
        api.getDailyStats(7).enqueue(new Callback<List<DailyStat>>() {

            @Override
            public void onResponse(Call<List<DailyStat>> call,
                                   Response<List<DailyStat>> response) {

                if (!response.isSuccessful() || response.body() == null) {
                    Log.e("API", "통계 응답 실패");
                    return;
                }

                activeDays.clear();
                dailyMinutesMap.clear();

                for (DailyStat stat : response.body()) {
                    int day = Integer.parseInt(stat.date.substring(8, 10));
                    int minutes = stat.durationSeconds / 60;

                    if (minutes > 0) {
                        activeDays.add(day);
                        dailyMinutesMap.put(day, minutes);
                    }
                }

                refreshCalendarUI();
                updateTodayCard(selectedDay);
            }

            @Override
            public void onFailure(Call<List<DailyStat>> call, Throwable t) {
                Log.e("API", "통계 로드 실패", t);
            }
        });
    }

    /**
     * ⏱ 선택된 날짜의 공부 시간을 오늘의 학습 카드에 반영
     */
    private void updateTodayCard(int day) {
        int minutes = dailyMinutesMap.containsKey(day)
                ? dailyMinutesMap.get(day)
                : 0;

        tvTodayMinutes.setText(String.valueOf(minutes));
        progressToday.setProgress(Math.min(minutes, 60));
    }

    /**
     * 🎨 캘린더 색상 갱신
     */
    private void refreshCalendarUI() {
        int rowCount = calendarGrid.getChildCount();

        for (int i = 0; i < rowCount; i++) {
            View child = calendarGrid.getChildAt(i);
            if (!(child instanceof LinearLayout)) continue;

            LinearLayout weekRow = (LinearLayout) child;
            int dayCount = weekRow.getChildCount();

            for (int j = 0; j < dayCount; j++) {
                View dayContainer = weekRow.getChildAt(j);
                if (!(dayContainer instanceof FrameLayout)) continue;

                FrameLayout frame = (FrameLayout) dayContainer;
                if (frame.getChildCount() == 0) continue;

                View v = frame.getChildAt(0);
                if (!(v instanceof TextView)) continue;
            }}}}


