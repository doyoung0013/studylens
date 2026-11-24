package com.studylens.client.model;

import com.google.gson.annotations.SerializedName;

import java.util.List;

public class StudyGroup {
    public long id;
    public String name;
    public String description;
    public UserBrief owner;

    @SerializedName("is_owner")
    public boolean isOwner;

    @SerializedName("member_count")
    public int memberCount;

    @SerializedName("invite_code")
    public String inviteCode;

    /** 상세 조회(GET /api/groups/{id}/)에서만 채워짐 */
    public List<UserBrief> members;
}
