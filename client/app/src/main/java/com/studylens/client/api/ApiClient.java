package com.studylens.client.api;

import android.content.Context;

import com.studylens.client.model.LoginResponse;
import com.studylens.client.model.RefreshRequest;
import com.studylens.client.util.Prefs;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;

public class ApiClient {

    public static final String BASE_URL = "https://doyoung.pythonanywhere.com/";

    private static Retrofit retrofit = null;

    /**
     * - 모든 요청에 저장된 access token 을 붙인다.
     * - 401 응답이면 refresh token 으로 한 번 갱신 후 재시도한다 (실패 시 토큰 삭제 → 다시 로그인 필요).
     */
    public static synchronized Retrofit getClient(Context context) {
        if (retrofit != null) return retrofit;

        Context app = context.getApplicationContext();

        // 토큰 갱신 전용 (인터셉터/Authenticator 없는 클라이언트)
        ApiService refreshApi = new Retrofit.Builder()
                .baseUrl(BASE_URL)
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(ApiService.class);

        OkHttpClient client = new OkHttpClient.Builder()
                .addInterceptor(chain -> {
                    Request original = chain.request();
                    String token = Prefs.getToken(app);
                    if (token == null || original.header("Authorization") != null) {
                        return chain.proceed(original);
                    }
                    return chain.proceed(original.newBuilder()
                            .header("Authorization", "Bearer " + token)
                            .build());
                })
                .authenticator((route, response) -> {
                    // 로그인 요청 실패이거나 이미 한 번 재시도한 요청이면 포기
                    if (response.request().url().encodedPath().endsWith("auth/login/")) return null;
                    if (response.priorResponse() != null) return null;

                    String refresh = Prefs.getRefreshToken(app);
                    if (refresh == null) return null;

                    retrofit2.Response<LoginResponse> res =
                            refreshApi.refresh(new RefreshRequest(refresh)).execute();
                    if (!res.isSuccessful() || res.body() == null) {
                        Prefs.clear(app);
                        return null;
                    }
                    Prefs.saveToken(app, res.body().access);
                    return response.request().newBuilder()
                            .header("Authorization", "Bearer " + res.body().access)
                            .build();
                })
                .build();

        retrofit = new Retrofit.Builder()
                .baseUrl(BASE_URL)
                .client(client)
                .addConverterFactory(GsonConverterFactory.create())
                .build();

        return retrofit;
    }
}
