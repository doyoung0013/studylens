package com.studylens.client.util;

import android.content.Context;
import android.content.SharedPreferences;

public class Prefs {

    private static final String PREF_NAME = "studylens";
    private static final String TOKEN = "token";
    private static final String REFRESH = "refresh";

    private static SharedPreferences prefs(Context ctx) {
        return ctx.getApplicationContext().getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE);
    }

    public static void saveTokens(Context ctx, String access, String refresh) {
        SharedPreferences.Editor e = prefs(ctx).edit().putString(TOKEN, access);
        if (refresh != null) e.putString(REFRESH, refresh);
        e.apply();
    }

    public static void saveToken(Context ctx, String token) {
        prefs(ctx).edit().putString(TOKEN, token).apply();
    }

    public static String getToken(Context ctx) {
        return prefs(ctx).getString(TOKEN, null);
    }

    public static String getRefreshToken(Context ctx) {
        return prefs(ctx).getString(REFRESH, null);
    }

    public static void clear(Context ctx) {
        prefs(ctx).edit().remove(TOKEN).remove(REFRESH).apply();
    }
}
