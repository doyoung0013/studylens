package com.studylens.client.util;

public class TimeFormat {

    /** 초 → "1시간 5분" / "42분" */
    public static String minutes(int seconds) {
        int totalMin = Math.max(0, seconds) / 60;
        int h = totalMin / 60;
        int m = totalMin % 60;
        if (h > 0) return h + "시간 " + m + "분";
        return m + "분";
    }

    /** 집중도(%) → "75%" / 기록 없으면 "-" */
    public static String rate(Double rate) {
        if (rate == null) return "-";
        return Math.round(rate) + "%";
    }
}
