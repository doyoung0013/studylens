package com.studylens.client.model;

/** 소셜 API 요청 바디 모음 */
public class SocialBodies {

    public static class Username {
        String username;
        public Username(String username) { this.username = username; }
    }

    public static class InviteCode {
        @com.google.gson.annotations.SerializedName("invite_code")
        String inviteCode;
        public InviteCode(String code) { this.inviteCode = code; }
    }

    public static class CreateGroup {
        String name;
        String description;
        public CreateGroup(String name, String description) {
            this.name = name;
            this.description = description;
        }
    }
}
