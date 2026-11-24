package com.studylens.client.ui;

import androidx.appcompat.app.AppCompatActivity;

import android.content.Intent;
import android.os.Bundle;
import android.widget.Button;
import android.widget.TextView;

import com.studylens.client.R;
import com.studylens.client.api.ApiClient;
import com.studylens.client.api.ApiService;
import com.studylens.client.model.DailyStat;
import com.studylens.client.util.TimeFormat;

import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.List;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

/** 특정 날짜의 공부 기록 상세 (EXTRA_DATE: yyyy-MM-dd) */
public class DailyDetailActivity extends AppCompatActivity {

    public static final String EXTRA_DATE = "date";

    TextView tvDate, tvStudyTime;
    Button btnGoGallery;
    ApiService api;
    LocalDate date;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_daily_detail);

        String raw = getIntent().getStringExtra(EXTRA_DATE);
        try {
            date = raw != null ? LocalDate.parse(raw) : LocalDate.now();
        } catch (DateTimeParseException e) {
            date = LocalDate.now();
        }

        tvDate = findViewById(R.id.tvDate);
        tvStudyTime = findViewById(R.id.tvStudyTime);
        btnGoGallery = findViewById(R.id.btnGoGallery);

        api = ApiClient.getClient(this).create(ApiService.class);

        tvDate.setText(date.getMonthValue() + "월 " + date.getDayOfMonth() + "일 공부 기록");

        loadDetail();

        btnGoGallery.setOnClickListener(v -> {
            Intent i = new Intent(this, StudyGalleryActivity.class);
            i.putExtra(StudyGalleryActivity.EXTRA_DATE, date.toString());
            startActivity(i);
        });
    }

    private void loadDetail() {
        String d = date.toString();
        api.getStatsRange(d, d).enqueue(new Callback<List<DailyStat>>() {
            @Override
            public void onResponse(Call<List<DailyStat>> call, Response<List<DailyStat>> response) {
                if (!response.isSuccessful() || response.body() == null || response.body().isEmpty()) {
                    tvStudyTime.setText("데이터 로드 실패");
                    return;
                }
                DailyStat s = response.body().get(0);
                if (s.totalSeconds == 0) {
                    tvStudyTime.setText("공부 기록 없음");
                    return;
                }
                tvStudyTime.setText("순공부 " + TimeFormat.minutes(s.focusSeconds)
                        + "\n전체 " + TimeFormat.minutes(s.totalSeconds)
                        + " · 딴짓 " + TimeFormat.minutes(s.distractedSeconds)
                        + " · 집중도 " + TimeFormat.rate(s.focusRate));
            }

            @Override
            public void onFailure(Call<List<DailyStat>> call, Throwable t) {
                tvStudyTime.setText("데이터 로드 실패");
            }
        });
    }
}
