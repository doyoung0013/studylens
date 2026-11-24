package com.studylens.client.api;

import com.studylens.client.model.*;

import java.util.List;

import retrofit2.Call;
import retrofit2.http.*;

public interface ApiService {

    // 로그인 (JWT)
    @POST("api/auth/login/")
    Call<LoginResponse> login(@Body LoginRequest body);

    // 액세스 토큰 갱신
    @POST("api/auth/refresh/")
    Call<LoginResponse> refresh(@Body RefreshRequest body);

    // 최근 N일 학습 통계
    @GET("api/stats/daily/")
    Call<List<DailyStat>> getDailyStats(@Query("days") int days);

    // 기간 학습 통계 (start, end: yyyy-MM-dd)
    @GET("api/stats/daily/")
    Call<List<DailyStat>> getStatsRange(@Query("start") String start, @Query("end") String end);

    // 특정 날짜 이미지 목록 (date: yyyy-MM-dd)
    @GET("api/gallery/")
    Call<List<StudyImage>> getGallery(@Query("date") String date);

    // 실시간 상태 (지금 공부 중인지, 몇 분째인지)
    @GET("api/study/current/")
    Call<CurrentStatus> getCurrent();
}
