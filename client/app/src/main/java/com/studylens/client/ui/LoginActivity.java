package com.studylens.client.ui;

import androidx.appcompat.app.AppCompatActivity;

import android.content.Intent;
import android.os.Bundle;
import android.widget.*;
import com.studylens.client.R;
import com.studylens.client.api.*;
import com.studylens.client.model.*;
import com.studylens.client.util.Prefs;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class LoginActivity extends AppCompatActivity {

    EditText usernameInput, passwordInput;
    Button loginBtn;
    ApiService api;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_login);

        usernameInput = findViewById(R.id.username);
        passwordInput = findViewById(R.id.password);
        loginBtn = findViewById(R.id.loginBtn);

        api = ApiClient.getClient(null).create(ApiService.class);

        loginBtn.setOnClickListener(v -> doLogin());
    }

    private void doLogin() {
        LoginRequest req = new LoginRequest(
                usernameInput.getText().toString(),
                passwordInput.getText().toString()
        );

        api.login(req).enqueue(new Callback<LoginResponse>() {
            @Override
            public void onResponse(Call<LoginResponse> call, Response<LoginResponse> res) {
                if (res.isSuccessful()) {
                    Prefs.saveToken(LoginActivity.this, res.body().access);
                    startActivity(new Intent(LoginActivity.this, HomeActivity.class));
                } else {
                    Toast.makeText(LoginActivity.this, "로그인 실패", Toast.LENGTH_SHORT).show();
                }
            }

            @Override
            public void onFailure(Call<LoginResponse> call, Throwable t) {
                Toast.makeText(LoginActivity.this, "서버 오류", Toast.LENGTH_SHORT).show();
            }
        });
    }
}
