package com.studylens.client.util;

import android.content.Context;
import android.content.SharedPreferences;

public class Prefs {

    private static final String PREF_NAME = "studylens";
    private static final String TOKEN = "token";

    public static void saveToken(Context ctx, String token) {
        ctx.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
                .edit().putString(TOKEN, token).apply();
    }

    public static String getToken(Context ctx) {
        return ctx.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
                .getString(TOKEN, null);
    }
}
