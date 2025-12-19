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

import java.util.ArrayList;
import java.util.List;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class StudyGalleryActivity extends AppCompatActivity {

    RecyclerView recyclerView;
    TextView tvTitle;
    ApiService api;
    int selectedDay;
    List<StudyImage> imageList = new ArrayList<>();
    ImageAdapter adapter;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_study_gallery);

        selectedDay = getIntent().getIntExtra("day", 1);

        recyclerView = findViewById(R.id.recyclerImages);
        tvTitle = findViewById(R.id.tvGalleryTitle);

        tvTitle.setText(selectedDay + "일 공부 모습");

        // ✅ Context 전달
        api = ApiClient
                .getClient(getApplicationContext())
                .create(ApiService.class);

        adapter = new ImageAdapter(this, imageList);

        recyclerView.setLayoutManager(new GridLayoutManager(this, 2));
        recyclerView.setAdapter(adapter);

        loadImages();
    }

    private void loadImages() {

        api.getImages(selectedDay).enqueue(new Callback<List<StudyImage>>() {
            @Override
            public void onResponse(Call<List<StudyImage>> call,
                                   Response<List<StudyImage>> response) {

                if (!response.isSuccessful()) {
                    Toast.makeText(
                            StudyGalleryActivity.this,
                            "이미지 로드 실패",
                            Toast.LENGTH_SHORT
                    ).show();
                    return;
                }

                imageList.clear();
                imageList.addAll(response.body());
                adapter.notifyDataSetChanged();
            }

            @Override
            public void onFailure(Call<List<StudyImage>> call, Throwable t) {
                Toast.makeText(
                        StudyGalleryActivity.this,
                        "서버 오류",
                        Toast.LENGTH_SHORT
                ).show();
            }
        });
    }
}
