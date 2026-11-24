package com.studylens.client.model;

public class SignupRequest {
    String username;
    String password;
    String password2;

    public SignupRequest(String username, String password, String password2) {
        this.username = username;
        this.password = password;
        this.password2 = password2;
    }
}
