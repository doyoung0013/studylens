package com.studylens.client.model;

/** GET /api/study/current/ 응답 (실시간 상태). */
public class CurrentStatus {
    public boolean studying;
    public SessionSummary session;   // 공부 중이 아니면 null
    public DailyStat today;
}
