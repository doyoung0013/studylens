package com.studylens.client.ui;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import com.studylens.client.R;
import com.studylens.client.api.ApiClient;
import com.studylens.client.api.ApiErrors;
import com.studylens.client.api.ApiService;
import com.studylens.client.model.FriendRequests;
import com.studylens.client.model.MessageResponse;
import com.studylens.client.model.RankingResponse;
import com.studylens.client.model.SocialBodies;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

/** 친구 추가 · 받은 요청 수락/거절 · 친구 순공부 랭킹 */
public class FriendsActivity extends AppCompatActivity {

    ApiService api;
    EditText inputUsername;
    Button btnAdd;
    LinearLayout requestContainer, rankingContainer;
    TextView tvRequestsEmpty;
    PeriodTabs periodTabs;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_friends);

        api = ApiClient.getClient(this).create(ApiService.class);

        inputUsername = findViewById(R.id.inputFriendUsername);
        btnAdd = findViewById(R.id.btnAddFriend);
        requestContainer = findViewById(R.id.requestContainer);
        rankingContainer = findViewById(R.id.rankingContainer);
        tvRequestsEmpty = findViewById(R.id.tvRequestsEmpty);

        periodTabs = new PeriodTabs(this, period -> loadRanking());
        btnAdd.setOnClickListener(v -> sendRequest());
    }

    @Override
    protected void onResume() {
        super.onResume();
        loadRequests();
        loadRanking();
    }

    private void toast(String msg) {
        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show();
    }

    // ---------------- 친구 요청 보내기 ----------------
    private void sendRequest() {
        String username = inputUsername.getText().toString().trim();
        if (username.isEmpty()) {
            toast("친구 아이디를 입력해 주세요");
            return;
        }
        btnAdd.setEnabled(false);
        api.sendFriendRequest(new SocialBodies.Username(username)).enqueue(new Callback<MessageResponse>() {
            @Override
            public void onResponse(Call<MessageResponse> call, Response<MessageResponse> res) {
                btnAdd.setEnabled(true);
                if (res.isSuccessful() && res.body() != null) {
                    toast(res.body().detail);
                    inputUsername.setText("");
                    if ("accepted".equals(res.body().status)) loadRanking();
                } else {
                    toast(ApiErrors.message(res, "요청에 실패했어요"));
                }
            }

            @Override
            public void onFailure(Call<MessageResponse> call, Throwable t) {
                btnAdd.setEnabled(true);
                toast("네트워크 오류");
            }
        });
    }

    // ---------------- 받은 요청 ----------------
    private void loadRequests() {
        api.getFriendRequests().enqueue(new Callback<FriendRequests>() {
            @Override
            public void onResponse(Call<FriendRequests> call, Response<FriendRequests> res) {
                if (!res.isSuccessful() || res.body() == null) return;
                renderRequests(res.body());
            }

            @Override
            public void onFailure(Call<FriendRequests> call, Throwable t) {
            }
        });
    }

    private void renderRequests(FriendRequests data) {
        requestContainer.removeAllViews();
        LayoutInflater inflater = LayoutInflater.from(this);
        for (FriendRequests.Item item : data.received) {
            View row = inflater.inflate(R.layout.item_friend_request, requestContainer, false);
            ((TextView) row.findViewById(R.id.tvRequestName)).setText(item.user.username);
            row.findViewById(R.id.btnAccept).setOnClickListener(v -> act(item.id, "accept"));
            row.findViewById(R.id.btnReject).setOnClickListener(v -> act(item.id, "reject"));
            requestContainer.addView(row);
        }
        tvRequestsEmpty.setVisibility(data.received.isEmpty() ? View.VISIBLE : View.GONE);
    }

    private void act(long requestId, String action) {
        api.friendRequestAction(requestId, action).enqueue(new Callback<MessageResponse>() {
            @Override
            public void onResponse(Call<MessageResponse> call, Response<MessageResponse> res) {
                if (res.isSuccessful() && res.body() != null) toast(res.body().detail);
                else toast(ApiErrors.message(res, "처리에 실패했어요"));
                loadRequests();
                loadRanking();
            }

            @Override
            public void onFailure(Call<MessageResponse> call, Throwable t) {
                toast("네트워크 오류");
            }
        });
    }

    // ---------------- 랭킹 ----------------
    private void loadRanking() {
        final String period = periodTabs.getSelected();
        api.getFriendRanking(period).enqueue(new Callback<RankingResponse>() {
            @Override
            public void onResponse(Call<RankingResponse> call, Response<RankingResponse> res) {
                if (!res.isSuccessful() || res.body() == null) return;
                if (!period.equals(periodTabs.getSelected())) return; // 그 사이 탭이 바뀜
                RankingRenderer.render(FriendsActivity.this, rankingContainer, res.body().ranking,
                        entry -> confirmDelete(entry));
            }

            @Override
            public void onFailure(Call<RankingResponse> call, Throwable t) {
                toast("랭킹을 불러오지 못했어요");
            }
        });
    }

    private void confirmDelete(RankingResponse.Entry entry) {
        new AlertDialog.Builder(this)
                .setTitle("친구 삭제")
                .setMessage(entry.username + "님을 친구에서 삭제할까요?")
                .setPositiveButton("삭제", (d, w) -> api.deleteFriend(entry.userId).enqueue(new Callback<Void>() {
                    @Override
                    public void onResponse(Call<Void> call, Response<Void> res) {
                        toast(res.isSuccessful() ? "삭제했어요" : ApiErrors.message(res, "삭제 실패"));
                        loadRanking();
                    }

                    @Override
                    public void onFailure(Call<Void> call, Throwable t) {
                        toast("네트워크 오류");
                    }
                }))
                .setNegativeButton("취소", null)
                .show();
    }
}
