package com.studylens.client.model;

import com.google.gson.annotations.SerializedName;

import java.util.List;

/** GET /api/friends/ranking/ , /api/groups/{id}/ranking/ */
public class RankingResponse {
    public String period;
    public String start;
    public String end;
    public List<Entry> ranking;

    public static class Entry {
        public int rank;

        @SerializedName("user_id")
        public long userId;

        public String username;

        @SerializedName("is_me")
        public boolean isMe;

        @SerializedName("studying_now")
        public boolean studyingNow;

        @SerializedName("total_seconds")
        public int totalSeconds;

        @SerializedName("focus_seconds")
        public int focusSeconds;

        @SerializedName("focus_rate")
        public Double focusRate;
    }
}
