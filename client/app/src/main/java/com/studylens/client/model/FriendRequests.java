package com.studylens.client.model;

import com.google.gson.annotations.SerializedName;

import java.util.List;

/** GET /api/friends/requests/ */
public class FriendRequests {
    public List<Item> received;
    public List<Item> sent;

    public static class Item {
        public long id;
        public UserBrief user;

        @SerializedName("created_at")
        public String createdAt;
    }
}
