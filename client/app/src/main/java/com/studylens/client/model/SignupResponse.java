package com.studylens.client.model;

/** POST /api/auth/signup/ 응답 — 가입과 동시에 토큰 발급 */
public class SignupResponse {
    public UserBrief user;
    public String access;
    public String refresh;
}
