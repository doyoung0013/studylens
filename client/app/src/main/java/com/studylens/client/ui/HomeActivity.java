package com.studylens.client.ui;

import androidx.appcompat.app.AppCompatActivity;

import android.content.Intent;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.*;
import com.studylens.client.R;
import com.studylens.client.api.*;
import com.studylens.client.model.*;
import com.studylens.client.util.Prefs;

import java.util.*;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class HomeActivity extends AppCompatActivity {

    GridLayout calendarGrid;
    Button btnGallery;
    int selectedDay = 12;
    ApiService api;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_home);

        calendarGrid = findViewById(R.id.calendarGrid);
        btnGallery = findViewById(R.id.btnGallery);

        api = ApiClient.getClient(null).create(ApiService.class);

        buildCalendar();
        loadStats();

        btnGallery.setOnClickListener(v -> {
            startActivity(new Intent(this, StudyGalleryActivity.class));
        });
    }

    private void buildCalendar() {
        for (int day = 1; day <= 31; day++) {
            int finalDay = day;

            TextView tv = new TextView(this);
            tv.setText(String.valueOf(day));
            tv.setPadding(20,20,20,20);
            tv.setGravity(Gravity.CENTER);
            tv.setBackgroundResource(R.drawable.calendar_day);
            tv.setOnClickListener(v -> {
                selectedDay = finalDay;
                loadStats();
            });
            calendarGrid.addView(tv);
        }
    }

    private void loadStats() {
        String token = "Bearer " + Prefs.getToken(this);

        api.getDailyStats(token, 7).enqueue(new Callback<List<DailyStat>>() {
            @Override
            public void onResponse(Call<List<DailyStat>> call, Response<List<DailyStat>> response) {
                if (!response.isSuccessful()) return;

                List<DailyStat> stats = response.body();
                // 오늘의 total_seconds 사용해서 UI 업데이트 가능
            }

            @Override
            public void onFailure(Call<List<DailyStat>> call, Throwable t) { }
        });
    }
}
