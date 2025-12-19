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

        api.getDailyStats(7).enqueue(new Callback<java.util.List<DailyStat>>() {
            @Override
            public void onResponse(Call<java.util.List<DailyStat>> call,
                                   Response<java.util.List<DailyStat>> response) {
                if (!response.isSuccessful()) return;

                for (DailyStat s : response.body()) {
                    if (s.day == selectedDay) {
                        int minutes = s.total_seconds / 60;
                        tvStudyTime.setText(minutes + "분 공부함");
                        break;
                    }
                }
            }

            @Override
            public void onFailure(Call<java.util.List<DailyStat>> call, Throwable t) { }
        });

    }
}
