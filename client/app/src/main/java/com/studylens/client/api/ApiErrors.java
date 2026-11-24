package com.studylens.client.api;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import retrofit2.Response;

/** 서버 에러 응답({"detail": "..."})에서 사용자에게 보여줄 메시지를 꺼낸다. */
public class ApiErrors {

    public static String message(Response<?> response, String fallback) {
        try {
            if (response.errorBody() != null) {
                JsonObject obj = new JsonParser().parse(response.errorBody().string()).getAsJsonObject();
                if (obj.has("detail")) return obj.get("detail").getAsString();
            }
        } catch (Exception ignored) {
        }
        if (response.code() == 429) return "요청이 너무 많아요. 잠시 후 다시 시도해 주세요.";
        return fallback + " (" + response.code() + ")";
    }
}
