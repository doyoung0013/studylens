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
import com.studylens.client.util.Prefs;

import java.util.List;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class DailyDetailActivity extends AppCompatActivity {

    TextView tvDate, tvStudyTime;
    Button btnGoGallery;
    ApiService api;
    int selectedDay;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_daily_detail);

        selectedDay = getIntent().getIntExtra("day", 1);

        tvDate = findViewById(R.id.tvDate);
        tvStudyTime = findViewById(R.id.tvStudyTime);
        btnGoGallery = findViewById(R.id.btnGoGallery);

        api = ApiClient.getClient(getApplicationContext()).create(ApiService.class);

        tvDate.setText(selectedDay + "일 공부 기록");

        loadDetail();

        btnGoGallery.setOnClickListener(v -> {
            Intent i = new Intent(this, StudyGalleryActivity.class);
            i.putExtra("day", selectedDay);
            startActivity(i);
        });
    }

    private void loadDetail() {
        String token = "Bearer " + Prefs.getToken(this);

        api.getDailyStats(7).enqueue(new Callback<List<DailyStat>>() {
            @Override
            public void onResponse(Call<List<DailyStat>> call,
                                   Response<List<DailyStat>> response) {

                if (!response.isSuccessful() || response.body() == null) return;

                for (DailyStat s : response.body()) {

                    // s.date 예: "2025-12-19"
                    // selectedDay 예: 19
                    int dayOfMonth = Integer.parseInt(s.date.substring(8, 10));

                    if (dayOfMonth == selectedDay) {
                        int minutes = s.durationSeconds / 60;
                        tvStudyTime.setText(minutes + "분 공부함");
                        return;
                    }
                }

                // 해당 날짜 데이터가 없는 경우
                tvStudyTime.setText("공부 기록 없음");
            }

            @Override
            public void onFailure(Call<List<DailyStat>> call, Throwable t) {
                tvStudyTime.setText("데이터 로드 실패");
            }
        });
    }


}
