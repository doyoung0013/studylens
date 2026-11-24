package com.studylens.client.ui;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

import android.content.Intent;
import android.os.Bundle;
import android.text.InputFilter;
import android.text.InputType;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import com.studylens.client.R;
import com.studylens.client.api.ApiClient;
import com.studylens.client.api.ApiErrors;
import com.studylens.client.api.ApiService;
import com.studylens.client.model.SocialBodies;
import com.studylens.client.model.StudyGroup;

import java.util.List;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

/** 내 스터디 그룹 목록 · 그룹 만들기 · 초대 코드로 참여 */
public class GroupsActivity extends AppCompatActivity {

    ApiService api;
    LinearLayout groupContainer;
    TextView tvEmpty;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_groups);

        api = ApiClient.getClient(this).create(ApiService.class);
        groupContainer = findViewById(R.id.groupContainer);
        tvEmpty = findViewById(R.id.tvGroupsEmpty);

        findViewById(R.id.btnCreateGroup).setOnClickListener(v -> showCreateDialog());
        findViewById(R.id.btnJoinGroup).setOnClickListener(v -> showJoinDialog());
    }

    @Override
    protected void onResume() {
        super.onResume();
        loadGroups();
    }

    private void toast(String msg) {
        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show();
    }

    private void loadGroups() {
        api.getGroups().enqueue(new Callback<List<StudyGroup>>() {
            @Override
            public void onResponse(Call<List<StudyGroup>> call, Response<List<StudyGroup>> res) {
                if (!res.isSuccessful() || res.body() == null) return;
                render(res.body());
            }

            @Override
            public void onFailure(Call<List<StudyGroup>> call, Throwable t) {
                toast("그룹 목록을 불러오지 못했어요");
            }
        });
    }

    private void render(List<StudyGroup> groups) {
        groupContainer.removeAllViews();
        LayoutInflater inflater = LayoutInflater.from(this);
        for (StudyGroup g : groups) {
            View row = inflater.inflate(R.layout.item_group, groupContainer, false);
            ((TextView) row.findViewById(R.id.tvItemGroupName)).setText(g.isOwner ? "👑 " + g.name : g.name);
            String info = g.memberCount + "명";
            if (g.description != null && !g.description.isEmpty()) info += " · " + g.description;
            ((TextView) row.findViewById(R.id.tvItemGroupInfo)).setText(info);
            row.setOnClickListener(v -> openGroup(g.id));
            groupContainer.addView(row);
        }
        tvEmpty.setVisibility(groups.isEmpty() ? View.VISIBLE : View.GONE);
    }

    private void openGroup(long id) {
        Intent i = new Intent(this, GroupDetailActivity.class);
        i.putExtra(GroupDetailActivity.EXTRA_GROUP_ID, id);
        startActivity(i);
    }

    private EditText input(String hint, int maxLength) {
        EditText et = new EditText(this);
        et.setHint(hint);
        et.setSingleLine(true);
        et.setFilters(new InputFilter[]{new InputFilter.LengthFilter(maxLength)});
        return et;
    }

    private LinearLayout padded(View... views) {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        int pad = Math.round(20 * getResources().getDisplayMetrics().density);
        box.setPadding(pad, pad / 2, pad, 0);
        for (View v : views) box.addView(v);
        return box;
    }

    private void showCreateDialog() {
        EditText name = input("그룹 이름 (최대 30자)", 30);
        EditText desc = input("소개 (선택)", 200);
        new AlertDialog.Builder(this)
                .setTitle("그룹 만들기")
                .setView(padded(name, desc))
                .setPositiveButton("만들기", (d, w) -> {
                    String n = name.getText().toString().trim();
                    if (n.isEmpty()) {
                        toast("그룹 이름을 입력해 주세요");
                        return;
                    }
                    api.createGroup(new SocialBodies.CreateGroup(n, desc.getText().toString().trim()))
                            .enqueue(groupCallback("그룹을 만들었어요", "그룹을 만들지 못했어요"));
                })
                .setNegativeButton("취소", null)
                .show();
    }

    private void showJoinDialog() {
        EditText code = input("초대 코드 8자리", 8);
        code.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS);
        new AlertDialog.Builder(this)
                .setTitle("초대 코드로 참여")
                .setView(padded(code))
                .setPositiveButton("참여", (d, w) -> {
                    String c = code.getText().toString().trim();
                    if (c.isEmpty()) return;
                    api.joinGroup(new SocialBodies.InviteCode(c))
                            .enqueue(groupCallback("그룹에 참여했어요", "참여하지 못했어요"));
                })
                .setNegativeButton("취소", null)
                .show();
    }

    /** 그룹 생성/참여 성공 시 바로 상세 화면으로 이동 */
    private Callback<StudyGroup> groupCallback(String okMessage, String failMessage) {
        return new Callback<StudyGroup>() {
            @Override
            public void onResponse(Call<StudyGroup> call, Response<StudyGroup> res) {
                if (res.isSuccessful() && res.body() != null) {
                    toast(okMessage);
                    openGroup(res.body().id);
                } else {
                    toast(ApiErrors.message(res, failMessage));
                }
            }

            @Override
            public void onFailure(Call<StudyGroup> call, Throwable t) {
                toast("네트워크 오류");
            }
        };
    }
}
