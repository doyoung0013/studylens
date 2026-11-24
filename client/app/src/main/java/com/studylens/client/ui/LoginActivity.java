package com.studylens.client.ui;

import androidx.appcompat.app.AppCompatActivity;

import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.widget.*;

import com.studylens.client.R;
import com.studylens.client.api.ApiClient;
import com.studylens.client.api.ApiService;
import com.studylens.client.model.LoginRequest;
import com.studylens.client.model.LoginResponse;
import com.studylens.client.util.Prefs;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class LoginActivity extends AppCompatActivity {

    EditText usernameInput, passwordInput;
    Button loginBtn;
    ApiService api;

    // 중복 클릭 & Toast 폭탄 방지용
    boolean isLoggingIn = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_login);

        usernameInput = findViewById(R.id.username);
        passwordInput = findViewById(R.id.password);
        loginBtn = findViewById(R.id.loginBtn);

        api = ApiClient
                .getClient(getApplicationContext())
                .create(ApiService.class);

        // 이미 로그인한 적이 있으면 바로 홈으로 (토큰이 만료됐으면 홈에서 자동 갱신/재로그인)
        if (Prefs.getToken(this) != null) {
            startActivity(new Intent(this, HomeActivity.class));
            finish();
            return;
        }

        findViewById(R.id.btnSignup).setOnClickListener(v ->
                startActivity(new Intent(this, SignupActivity.class)));

        loginBtn.setOnClickListener(v -> {
            if (!isLoggingIn) {
                doLogin();
            }
        });
    }

    private void doLogin() {
        isLoggingIn = true;
        loginBtn.setEnabled(false);

        LoginRequest req = new LoginRequest(
                usernameInput.getText().toString(),
                passwordInput.getText().toString()
        );

        api.login(req).enqueue(new Callback<LoginResponse>() {
            @Override
            public void onResponse(Call<LoginResponse> call, Response<LoginResponse> res) {

                Log.d("LOGIN", "onResponse code=" + res.code());

                isLoggingIn = false;
                loginBtn.setEnabled(true);

                if (res.isSuccessful() && res.body() != null) {

                    // ✅ access / refresh token 저장
                    Prefs.saveTokens(LoginActivity.this, res.body().access, res.body().refresh);

                    startActivity(
                            new Intent(LoginActivity.this, HomeActivity.class)
                    );
                    finish();

                } else {
                    try {
                        if (res.errorBody() != null) {
                            Log.d("LOGIN", "errorBody=" + res.errorBody().string());
                        }
                    } catch (Exception ignored) {}

                    Toast.makeText(
                            LoginActivity.this,
                            res.code() == 401
                                    ? "아이디 또는 비밀번호가 틀렸습니다"
                                    : "서버 응답 오류 (" + res.code() + ")",
                            Toast.LENGTH_SHORT
                    ).show();
                }
            }

            @Override
            public void onFailure(Call<LoginResponse> call, Throwable t) {

                isLoggingIn = false;
                loginBtn.setEnabled(true);

                Log.e("LOGIN", "onFailure", t);

                Toast.makeText(
                        LoginActivity.this,
                        "네트워크 오류: " + t.getMessage(),
                        Toast.LENGTH_SHORT
                ).show();
            }
        });
    }
}
