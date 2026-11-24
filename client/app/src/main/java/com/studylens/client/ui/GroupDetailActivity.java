package com.studylens.client.ui;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.os.Bundle;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import com.studylens.client.R;
import com.studylens.client.api.ApiClient;
import com.studylens.client.api.ApiErrors;
import com.studylens.client.api.ApiService;
import com.studylens.client.model.InviteCodeResponse;
import com.studylens.client.model.MessageResponse;
import com.studylens.client.model.RankingResponse;
import com.studylens.client.model.StudyGroup;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

/** 스터디 그룹 상세 — 초대 코드 공유 · 멤버 순공부 랭킹 · 나가기 */
public class GroupDetailActivity extends AppCompatActivity {

    public static final String EXTRA_GROUP_ID = "group_id";

    ApiService api;
    long groupId;
    StudyGroup group;

    TextView tvName, tvDesc, tvCode, tvMembers, btnRegen;
    LinearLayout rankingContainer;
    PeriodTabs periodTabs;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_group_detail);

        groupId = getIntent().getLongExtra(EXTRA_GROUP_ID, -1);
        api = ApiClient.getClient(this).create(ApiService.class);

        tvName = findViewById(R.id.tvGroupName);
        tvDesc = findViewById(R.id.tvGroupDesc);
        tvCode = findViewById(R.id.tvInviteCode);
        tvMembers = findViewById(R.id.tvMemberCount);
        btnRegen = findViewById(R.id.btnRegenCode);
        rankingContainer = findViewById(R.id.rankingContainer);

        periodTabs = new PeriodTabs(this, period -> loadRanking());

        findViewById(R.id.btnCopyCode).setOnClickListener(v -> copyCode());
        btnRegen.setOnClickListener(v -> regenerateCode());
        findViewById(R.id.btnLeaveGroup).setOnClickListener(v -> confirmLeave());

        loadGroup();
        loadRanking();
    }

    private void toast(String msg) {
        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show();
    }

    private void loadGroup() {
        api.getGroup(groupId).enqueue(new Callback<StudyGroup>() {
            @Override
            public void onResponse(Call<StudyGroup> call, Response<StudyGroup> res) {
                if (!res.isSuccessful() || res.body() == null) {
                    toast(ApiErrors.message(res, "그룹을 찾을 수 없어요"));
                    finish();
                    return;
                }
                group = res.body();
                tvName.setText(group.name);
                boolean hasDesc = group.description != null && !group.description.isEmpty();
                tvDesc.setText(hasDesc ? group.description : "");
                tvDesc.setVisibility(hasDesc ? View.VISIBLE : View.GONE);
                tvCode.setText(group.inviteCode);
                tvMembers.setText("멤버 " + group.memberCount + "명 · 방장 " + group.owner.username);
                btnRegen.setVisibility(group.isOwner ? View.VISIBLE : View.GONE);
            }

            @Override
            public void onFailure(Call<StudyGroup> call, Throwable t) {
                toast("네트워크 오류");
            }
        });
    }

    private void loadRanking() {
        final String period = periodTabs.getSelected();
        api.getGroupRanking(groupId, period).enqueue(new Callback<RankingResponse>() {
            @Override
            public void onResponse(Call<RankingResponse> call, Response<RankingResponse> res) {
                if (!res.isSuccessful() || res.body() == null) return;
                if (!period.equals(periodTabs.getSelected())) return;
                RankingRenderer.render(GroupDetailActivity.this, rankingContainer, res.body().ranking, null);
            }

            @Override
            public void onFailure(Call<RankingResponse> call, Throwable t) {
                toast("랭킹을 불러오지 못했어요");
            }
        });
    }

    private void copyCode() {
        if (group == null) return;
        ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        cm.setPrimaryClip(ClipData.newPlainText("StudyLens 초대 코드", group.inviteCode));
        toast("초대 코드를 복사했어요");
    }

    private void regenerateCode() {
        new AlertDialog.Builder(this)
                .setTitle("초대 코드 재발급")
                .setMessage("기존 초대 코드는 더 이상 사용할 수 없게 됩니다.")
                .setPositiveButton("재발급", (d, w) -> api.regenerateInviteCode(groupId).enqueue(new Callback<InviteCodeResponse>() {
                    @Override
                    public void onResponse(Call<InviteCodeResponse> call, Response<InviteCodeResponse> res) {
                        if (res.isSuccessful() && res.body() != null) {
                            group.inviteCode = res.body().inviteCode;
                            tvCode.setText(group.inviteCode);
                            toast("새 초대 코드가 발급됐어요");
                        } else {
                            toast(ApiErrors.message(res, "재발급 실패"));
                        }
                    }

                    @Override
                    public void onFailure(Call<InviteCodeResponse> call, Throwable t) {
                        toast("네트워크 오류");
                    }
                }))
                .setNegativeButton("취소", null)
                .show();
    }

    private void confirmLeave() {
        String extra = group != null && group.isOwner
                ? "\n방장이 나가면 가장 먼저 가입한 멤버가 방장이 됩니다." : "";
        new AlertDialog.Builder(this)
                .setTitle("그룹 나가기")
                .setMessage("이 그룹에서 나갈까요?" + extra)
                .setPositiveButton("나가기", (d, w) -> api.leaveGroup(groupId).enqueue(new Callback<MessageResponse>() {
                    @Override
                    public void onResponse(Call<MessageResponse> call, Response<MessageResponse> res) {
                        if (res.isSuccessful() && res.body() != null) {
                            toast(res.body().detail);
                            finish();
                        } else {
                            toast(ApiErrors.message(res, "나가지 못했어요"));
                        }
                    }

                    @Override
                    public void onFailure(Call<MessageResponse> call, Throwable t) {
                        toast("네트워크 오류");
                    }
                }))
                .setNegativeButton("취소", null)
                .show();
    }
}
