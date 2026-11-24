package com.studylens.client.ui;

import androidx.appcompat.app.AppCompatActivity;
import androidx.recyclerview.widget.GridLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import android.os.Bundle;
import android.widget.TextView;
import android.widget.Toast;

import com.studylens.client.R;
import com.studylens.client.adapter.ImageAdapter;
import com.studylens.client.api.ApiClient;
import com.studylens.client.api.ApiService;
import com.studylens.client.model.StudyImage;

import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.List;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class StudyGalleryActivity extends AppCompatActivity {

    /** 조회할 날짜 (yyyy-MM-dd). 없으면 오늘 */
    public static final String EXTRA_DATE = "date";

    RecyclerView recyclerView;
    TextView tvTitle;
    ApiService api;
    LocalDate date;
    List<StudyImage> imageList = new ArrayList<>();
    ImageAdapter adapter;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_study_gallery);

        date = parseDate(getIntent().getStringExtra(EXTRA_DATE));

        recyclerView = findViewById(R.id.recyclerImages);
        tvTitle = findViewById(R.id.tvGalleryTitle);

        tvTitle.setText(date.equals(LocalDate.now())
                ? "오늘의 공부 모습"
                : date.getMonthValue() + "월 " + date.getDayOfMonth() + "일 공부 모습");

        api = ApiClient.getClient(this).create(ApiService.class);

        adapter = new ImageAdapter(this, imageList);
        recyclerView.setLayoutManager(new GridLayoutManager(this, 2));
        recyclerView.setAdapter(adapter);

        loadImages();
    }

    private static LocalDate parseDate(String value) {
        if (value == null) return LocalDate.now();
        try {
            return LocalDate.parse(value);
        } catch (DateTimeParseException e) {
            return LocalDate.now();
        }
    }

    private void loadImages() {
        api.getGallery(date.toString()).enqueue(new Callback<List<StudyImage>>() {
            @Override
            public void onResponse(Call<List<StudyImage>> call, Response<List<StudyImage>> response) {
                if (!response.isSuccessful() || response.body() == null) {
                    Toast.makeText(StudyGalleryActivity.this, "이미지 로드 실패", Toast.LENGTH_SHORT).show();
                    return;
                }
                imageList.clear();
                imageList.addAll(response.body());
                adapter.notifyDataSetChanged();
                if (imageList.isEmpty()) {
                    Toast.makeText(StudyGalleryActivity.this, "이 날은 촬영된 공부 모습이 없어요", Toast.LENGTH_SHORT).show();
                }
            }

            @Override
            public void onFailure(Call<List<StudyImage>> call, Throwable t) {
                Toast.makeText(StudyGalleryActivity.this, "서버 오류", Toast.LENGTH_SHORT).show();
            }
        });
    }
}
