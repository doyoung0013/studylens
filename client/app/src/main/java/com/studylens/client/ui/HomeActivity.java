package com.studylens.client.ui;

import androidx.appcompat.app.AppCompatActivity;

import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.*;

import com.studylens.client.R;
import com.studylens.client.api.*;
import com.studylens.client.model.*;

import java.util.*;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class HomeActivity extends AppCompatActivity {

    LinearLayout calendarGrid;
    Button btnGallery;
    ApiService api;

    // 현재 선택된 날짜의 TextView를 기억해두는 변수
    TextView selectedDateView = null;
    int selectedDay = 19; // 초기 선택 날짜 (오늘)

    // ★ 공부한 날짜들 (초록색으로 복구하기 위해 필요)
    // 실제로는 서버에서 받아와야 하지만, 디자인 유지를 위해 일단 하드코딩 리스트 사용
    List<Integer> activeDays = Arrays.asList(2, 3, 4, 10, 11, 15, 16);

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_home);

        calendarGrid = findViewById(R.id.calendarGrid);
        btnGallery = findViewById(R.id.btnGallery);

        api = ApiClient.getClient(getApplicationContext()).create(ApiService.class);

        // 캘린더 이벤트 연결
        setupCalendarEvents();

        // 초기 데이터 로드
        loadStats();

        btnGallery.setOnClickListener(v -> {
            startActivity(new Intent(this, StudyGalleryActivity.class));
        });
    }

    private void setupCalendarEvents() {
        int rowCount = calendarGrid.getChildCount();

        for (int i = 0; i < rowCount; i++) {
            View child = calendarGrid.getChildAt(i);
            if (child instanceof LinearLayout) {
                LinearLayout weekRow = (LinearLayout) child;
                int dayCount = weekRow.getChildCount();

                for (int j = 0; j < dayCount; j++) {
                    View dayContainer = weekRow.getChildAt(j);
                    if (dayContainer instanceof FrameLayout) {
                        FrameLayout frame = (FrameLayout) dayContainer;
                        if (frame.getChildCount() > 0) {
                            View view = frame.getChildAt(0);
                            if (view instanceof TextView) {
                                TextView dayTextView = (TextView) view;
                                String dayText = dayTextView.getText().toString();

                                if (!dayText.isEmpty()) {
                                    int dayNum = Integer.parseInt(dayText);

                                    // 1. 초기 선택된 날짜(19일) 찾아서 변수에 저장해두기
                                    if (dayNum == selectedDay) {
                                        selectedDateView = dayTextView;
                                    }

                                    // 2. 클릭 이벤트 연결
                                    dayTextView.setOnClickListener(v -> {
                                        handleDateClick(dayTextView, dayNum);
                                    });
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // ★ 날짜 클릭 시 디자인 변경 로직
    private void handleDateClick(TextView newView, int newDay) {
        // 이미 선택된 날짜를 또 누르면 무시
        if (selectedDateView == newView) return;

        // 1. [이전 날짜 복구] 원래 색상으로 되돌리기
        if (selectedDateView != null) {
            int prevDay = Integer.parseInt(selectedDateView.getText().toString());

            if (activeDays.contains(prevDay)) {
                // 공부한 날이었으면 -> 초록 동그라미 복구
                selectedDateView.setBackgroundResource(R.drawable.bg_day_active);
                selectedDateView.setTextColor(Color.parseColor("#15803d")); // 진한 초록
            } else {
                // 평범한 날이었으면 -> 배경 투명, 글씨 회색 복구
                selectedDateView.setBackground(null);
                selectedDateView.setTextColor(Color.parseColor("#4B5563")); // 회색
            }
        }

        // 2. [새 날짜 선택] 검은색 동그라미 적용
        newView.setBackgroundResource(R.drawable.bg_day_selected);
        newView.setTextColor(Color.WHITE);

        // 3. 변수 업데이트
        selectedDateView = newView;
        selectedDay = newDay;

        // 4. 데이터 로드 및 피드백
        Toast.makeText(this, selectedDay + "일 선택됨", Toast.LENGTH_SHORT).show();
        loadStats();
    }

    private void loadStats() {
        api.getDailyStats(7).enqueue(new Callback<List<DailyStat>>() {
            @Override
            public void onResponse(Call<List<DailyStat>> call, Response<List<DailyStat>> response) {
                if (response.isSuccessful()) {
                    Log.d("API", selectedDay + "일 데이터 로드 성공");
                }
            }
            @Override
            public void onFailure(Call<List<DailyStat>> call, Throwable t) {}
        });
    }
}