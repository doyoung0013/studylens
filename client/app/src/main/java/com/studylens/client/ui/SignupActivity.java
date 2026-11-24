package com.studylens.client.ui;

import androidx.appcompat.app.AppCompatActivity;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;

import com.studylens.client.R;
import com.studylens.client.api.ApiClient;
import com.studylens.client.api.ApiErrors;
import com.studylens.client.api.ApiService;
import com.studylens.client.model.SignupRequest;
import com.studylens.client.model.SignupResponse;
import com.studylens.client.util.Prefs;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

/** 회원가입 — 가입 성공 시 바로 로그인 상태로 홈 이동 */
public class SignupActivity extends AppCompatActivity {

    EditText inputUsername, inputPassword, inputPassword2;
    TextView tvError;
    Button btnSignup;
    ApiService api;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_signup);

        inputUsername = findViewById(R.id.signupUsername);
        inputPassword = findViewById(R.id.signupPassword);
        inputPassword2 = findViewById(R.id.signupPassword2);
        tvError = findViewById(R.id.signupError);
        btnSignup = findViewById(R.id.btnDoSignup);

        api = ApiClient.getClient(this).create(ApiService.class);

        btnSignup.setOnClickListener(v -> doSignup());
        findViewById(R.id.btnGoLogin).setOnClickListener(v -> finish());
    }

    private void showError(String message) {
        tvError.setText(message);
        tvError.setVisibility(View.VISIBLE);
    }

    private void doSignup() {
        String username = inputUsername.getText().toString().trim();
        String pw = inputPassword.getText().toString();
        String pw2 = inputPassword2.getText().toString();

        // 간단한 클라이언트 검증 (최종 검증은 서버)
        if (!username.matches("^[A-Za-z0-9_.]{4,20}$")) {
            showError("아이디는 영문, 숫자, _ . 조합 4~20자여야 합니다.");
            return;
        }
        if (pw.length() < 8) {
            showError("비밀번호는 8자 이상이어야 합니다.");
            return;
        }
        if (!pw.equals(pw2)) {
            showError("비밀번호가 일치하지 않습니다.");
            return;
        }

        tvError.setVisibility(View.GONE);
        btnSignup.setEnabled(false);

        api.signup(new SignupRequest(username, pw, pw2)).enqueue(new Callback<SignupResponse>() {
            @Override
            public void onResponse(Call<SignupResponse> call, Response<SignupResponse> res) {
                btnSignup.setEnabled(true);
                if (res.isSuccessful() && res.body() != null) {
                    Prefs.saveTokens(SignupActivity.this, res.body().access, res.body().refresh);
                    Intent i = new Intent(SignupActivity.this, HomeActivity.class);
                    i.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
                    startActivity(i);
                    finish();
                } else {
                    showError(ApiErrors.message(res, "가입에 실패했어요"));
                }
            }

            @Override
            public void onFailure(Call<SignupResponse> call, Throwable t) {
                btnSignup.setEnabled(true);
                showError("네트워크 오류: " + t.getMessage());
            }
        });
    }
}
