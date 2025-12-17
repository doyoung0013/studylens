package com.studylens.client.api;

import com.studylens.client.model.*;

import java.util.List;

import okhttp3.MultipartBody;
import retrofit2.Call;
import retrofit2.http.*;

public interface ApiService {

    // 로그인 (JWT)
    @POST("auth/login/")
    Call<LoginResponse> login(@Body LoginRequest body);

    // 오늘 날짜 학습 통계
    @GET("stats/daily/")
    Call<List<DailyStat>> getDailyStats(@Header("Authorization") String token, @Query("days") int days);

    // 오늘의 이미지 목록
    @GET("gallery/today/")
    Call<List<StudyImage>> getTodayGallery(@Header("Authorization") String token);

    @GET("study/images/")
    Call<List<StudyImage>> getImages(
            @Header("Authorization") String token,
            @Query("day") int day
    );

}
