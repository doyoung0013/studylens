package com.studylens.client.model;

public class LoginRequest {
    String username;
    String password;

    public LoginRequest(String u, String p) {
        this.username = u;
        this.password = p;
    }
}
