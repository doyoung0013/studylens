package com.studylens.client.api;

import com.studylens.client.model.*;

import java.util.List;

import retrofit2.Call;
import retrofit2.http.*;

public interface ApiService {

    // 로그인 (JWT)
    @POST("api/auth/login/")
    Call<LoginResponse> login(@Body LoginRequest body);

    // 최근 N일 학습 통계
    @GET("api/stats/daily/")
    Call<List<DailyStat>> getDailyStats(@Query("days") int days);

    // 오늘의 이미지 목록
    @GET("api/gallery/today/")
    Call<List<StudyImage>> getTodayGallery();

    // 특정 날짜 이미지 목록
    @GET("api/study/images/")
    Call<List<StudyImage>> getImages(
            @Query("day") int day
    );


}
