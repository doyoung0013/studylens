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

    // ================= 회원가입 / 내 정보 =================

    @POST("api/auth/signup/")
    Call<SignupResponse> signup(@Body SignupRequest body);

    @GET("api/me/")
    Call<MeResponse> getMe();

    // ================= 친구 =================

    @GET("api/friends/requests/")
    Call<FriendRequests> getFriendRequests();

    @POST("api/friends/requests/")
    Call<MessageResponse> sendFriendRequest(@Body SocialBodies.Username body);

    /** action: accept | reject | cancel */
    @POST("api/friends/requests/{id}/{action}/")
    Call<MessageResponse> friendRequestAction(@Path("id") long requestId, @Path("action") String action);

    @DELETE("api/friends/{userId}/")
    Call<Void> deleteFriend(@Path("userId") long userId);

    /** period: today | week | month */
    @GET("api/friends/ranking/")
    Call<RankingResponse> getFriendRanking(@Query("period") String period);

    // ================= 스터디 그룹 =================

    @GET("api/groups/")
    Call<List<StudyGroup>> getGroups();

    @POST("api/groups/")
    Call<StudyGroup> createGroup(@Body SocialBodies.CreateGroup body);

    @POST("api/groups/join/")
    Call<StudyGroup> joinGroup(@Body SocialBodies.InviteCode body);

    @GET("api/groups/{id}/")
    Call<StudyGroup> getGroup(@Path("id") long groupId);

    @POST("api/groups/{id}/leave/")
    Call<MessageResponse> leaveGroup(@Path("id") long groupId);

    @POST("api/groups/{id}/invite-code/")
    Call<InviteCodeResponse> regenerateInviteCode(@Path("id") long groupId);

    @GET("api/groups/{id}/ranking/")
    Call<RankingResponse> getGroupRanking(@Path("id") long groupId, @Query("period") String period);
}
