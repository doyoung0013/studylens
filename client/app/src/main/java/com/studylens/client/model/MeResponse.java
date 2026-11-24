package com.studylens.client.model;

import com.google.gson.annotations.SerializedName;

public class MeResponse {
    public long id;
    public String username;

    @SerializedName("daily_goal_minutes")
    public int dailyGoalMinutes;

    @SerializedName("friend_count")
    public int friendCount;

    @SerializedName("pending_friend_requests")
    public int pendingFriendRequests;

    @SerializedName("group_count")
    public int groupCount;
}
