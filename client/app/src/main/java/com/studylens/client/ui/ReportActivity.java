package com.studylens.client.ui;

import androidx.appcompat.app.AppCompatActivity;

import android.graphics.Color;
import android.os.Bundle;
import android.util.TypedValue;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import com.studylens.client.R;
import com.studylens.client.api.ApiClient;
import com.studylens.client.api.ApiErrors;
import com.studylens.client.api.ApiService;
import com.studylens.client.model.DailyStat;
import com.studylens.client.model.ReportResponse;
import com.studylens.client.util.TimeFormat;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

/**
 * 학습 리포트 — 오늘 / 최근 7일 / 이번 달
 * 요약 카드, 한 줄 요약, 목표 달성 그래프, 시간대별 집중 그래프, 25분+ 연속 집중 구간, 자리 이탈·휴대폰 빈도
 */
public class ReportActivity extends AppCompatActivity {

    ApiService api;
    PeriodTabs periodTabs;

    TextView tvRange, tvGoalReport, tvBestHours, tvDeepSummary;
    LinearLayout statRow1, statRow2, statRow3, insightContainer, deepContainer;
    BarChartView goalChart, hourlyChart;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_report);

        api = ApiClient.getClient(this).create(ApiService.class);

        tvRange = findViewById(R.id.tvReportRange);
        tvGoalReport = findViewById(R.id.tvGoalReport);
        tvBestHours = findViewById(R.id.tvBestHours);
        tvDeepSummary = findViewById(R.id.tvDeepSummary);
        statRow1 = findViewById(R.id.statRow1);
        statRow2 = findViewById(R.id.statRow2);
        statRow3 = findViewById(R.id.statRow3);
        insightContainer = findViewById(R.id.insightContainer);
        deepContainer = findViewById(R.id.deepContainer);
        goalChart = findViewById(R.id.reportGoalChart);
        hourlyChart = findViewById(R.id.hourlyChart);

        periodTabs = new PeriodTabs(this, period -> load());
        load();
    }

    private void load() {
        final String period = periodTabs.getSelected();
        api.getReport(period).enqueue(new Callback<ReportResponse>() {
            @Override
            public void onResponse(Call<ReportResponse> call, Response<ReportResponse> res) {
                if (!res.isSuccessful() || res.body() == null) {
                    Toast.makeText(ReportActivity.this, ApiErrors.message(res, "리포트를 불러오지 못했어요"),
                            Toast.LENGTH_SHORT).show();
                    return;
                }
                if (!period.equals(periodTabs.getSelected())) return;
                render(res.body());
            }

            @Override
            public void onFailure(Call<ReportResponse> call, Throwable t) {
                Toast.makeText(ReportActivity.this, "네트워크 오류", Toast.LENGTH_SHORT).show();
            }
        });
    }

    // ==============================================================
    private void render(ReportResponse r) {
        tvRange.setText(r.start.equals(r.end) ? r.start : r.start + " ~ " + r.end);

        // ---- 요약 카드 ----
        statRow1.removeAllViews();
        statRow2.removeAllViews();
        addStat(statRow1, "순공부", TimeFormat.minutes(r.totals.focusSeconds),
                "전체 " + TimeFormat.minutes(r.totals.totalSeconds));
        addStat(statRow1, "집중도", TimeFormat.rate(r.totals.focusRate),
                "딴짓 " + TimeFormat.minutes(r.totals.distractedSeconds));
        addStat(statRow2, "목표 달성", r.goal.achievedDays + " / " + r.goal.days + "일",
                "하루 " + TimeFormat.minutes(r.goal.dailyGoalMinutes * 60));
        Double change = r.comparison.changeRate;
        addStat(statRow2, "이전 기간 대비",
                change == null ? "-" : (change >= 0 ? "▲ " : "▼ ") + Math.abs(Math.round(change)) + "%",
                "연속 공부 " + r.streak.currentDays + "일");

        // ---- 한 줄 요약 ----
        insightContainer.removeAllViews();
        for (String line : r.insights) {
            TextView tv = new TextView(this);
            tv.setText("• " + line);
            tv.setTextColor(Color.parseColor("#374151"));
            tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
            tv.setPadding(0, dp(3), 0, dp(3));
            insightContainer.addView(tv);
        }

        renderGoalChart(r);
        renderHourly(r);
        renderDeepFocus(r);

        // ---- 자리 이탈 / 휴대폰 ----
        statRow3.removeAllViews();
        addStat(statRow3, "자리 이탈", r.away.count + "회",
                (r.away.perHour != null ? "1시간당 " + r.away.perHour + "회 · " : "")
                        + TimeFormat.minutes(r.away.totalSeconds));
        addStat(statRow3, "휴대폰 사용", r.phone.count + "회",
                (r.phone.perHour != null ? "1시간당 " + r.phone.perHour + "회 · " : "")
                        + TimeFormat.minutes(r.phone.totalSeconds));
    }

    private void renderGoalChart(ReportResponse r) {
        List<DailyStat> days = r.daily;
        int n = days.size();
        float[] values = new float[n];
        int[] colors = new int[n];
        String[] labels = new String[n];
        for (int i = 0; i < n; i++) {
            DailyStat d = days.get(i);
            values[i] = d.focusSeconds / 60f;
            colors[i] = Color.parseColor(d.goalAchieved ? "#16A34A" : "#A5B4FC");
            LocalDate date = LocalDate.parse(d.date);
            // 한 달 보기에서는 라벨이 겹치지 않도록 5일 간격만 표시
            labels[i] = (n <= 7 || date.getDayOfMonth() == 1 || date.getDayOfMonth() % 5 == 0)
                    ? date.getMonthValue() + "/" + date.getDayOfMonth() : "";
        }
        goalChart.setData(values, colors, labels, null, r.goal.dailyGoalMinutes,
                "목표 " + r.goal.dailyGoalMinutes + "분");

        String rate = r.goal.achievementRate == null ? "-" : Math.round(r.goal.achievementRate) + "%";
        tvGoalReport.setText(r.goal.days + "일 중 " + r.goal.achievedDays + "일 달성 (" + rate + ")"
                + " · 연속 달성 " + r.streak.goalCurrentDays + "일");
    }

    private void renderHourly(ReportResponse r) {
        Set<Integer> best = new HashSet<>();
        for (ReportResponse.BestHour b : r.bestHours) best.add(b.hour);

        float[] values = new float[24];
        int[] colors = new int[24];
        String[] labels = new String[24];
        for (ReportResponse.Hour h : r.hourly) {
            values[h.hour] = h.focusSeconds / 60f;
            colors[h.hour] = Color.parseColor(best.contains(h.hour) ? "#4F46E5" : "#C7D2FE");
            labels[h.hour] = h.hour % 6 == 0 ? h.hour + "시" : "";
        }
        hourlyChart.setData(values, colors, labels, null, -1, null);

        if (r.bestHours.isEmpty()) {
            tvBestHours.setText("아직 기록이 없어요");
        } else {
            StringBuilder sb = new StringBuilder("가장 집중이 잘 되는 시간\n");
            for (int i = 0; i < r.bestHours.size(); i++) {
                ReportResponse.BestHour b = r.bestHours.get(i);
                sb.append(i + 1).append(". ").append(b.label)
                        .append(" (").append(TimeFormat.minutes(b.focusSeconds)).append(")");
                if (i < r.bestHours.size() - 1) sb.append("\n");
            }
            if (r.bestTimeBand != null) sb.append("\n\n주로 ").append(r.bestTimeBand.label).append("에 공부해요");
            tvBestHours.setText(sb.toString());
        }
    }

    private void renderDeepFocus(ReportResponse r) {
        ReportResponse.DeepFocus d = r.deepFocus;
        tvDeepSummary.setText(d.count == 0
                ? "아직 " + d.thresholdMinutes + "분 이상 이어진 집중 구간이 없어요"
                : d.count + "회 · 합계 " + TimeFormat.minutes(d.totalSeconds)
                + " · 최장 " + TimeFormat.minutes(d.longestSeconds));

        deepContainer.removeAllViews();
        DateTimeFormatter fmt = DateTimeFormatter.ofPattern("M/d HH:mm");
        for (ReportResponse.Block b : d.blocks) {
            TextView tv = new TextView(this);
            String start = OffsetDateTime.parse(b.start).atZoneSameInstant(ZoneId.systemDefault()).format(fmt);
            String end = OffsetDateTime.parse(b.end).atZoneSameInstant(ZoneId.systemDefault())
                    .format(DateTimeFormatter.ofPattern("HH:mm"));
            tv.setText(start + " ~ " + end + "   " + b.minutes + "분");
            tv.setTextColor(Color.parseColor("#6B7280"));
            tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13);
            tv.setPadding(0, dp(3), 0, dp(3));
            deepContainer.addView(tv);
        }
    }

    // ==============================================================
    private void addStat(LinearLayout row, String label, String value, String sub) {
        View card = LayoutInflater.from(this).inflate(R.layout.view_report_stat, row, false);
        ((TextView) card.findViewById(R.id.tvStatLabel)).setText(label);
        ((TextView) card.findViewById(R.id.tvStatValue)).setText(value);
        ((TextView) card.findViewById(R.id.tvStatSub)).setText(sub);
        row.addView(card);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
