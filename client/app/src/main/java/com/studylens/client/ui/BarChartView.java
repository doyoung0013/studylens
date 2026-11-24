package com.studylens.client.ui;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.DashPathEffect;
import android.graphics.Paint;
import android.graphics.RectF;
import android.util.AttributeSet;
import android.view.View;

/**
 * 외부 라이브러리 없이 그리는 간단한 막대 그래프.
 * - 막대별 색상, 아래 라벨, 위 값 텍스트(선택), 목표선(선택)
 * 목표 달성 그래프(홈·리포트)와 시간대별 집중 그래프(리포트)에 사용한다.
 */
public class BarChartView extends View {

    private float[] values = new float[0];
    private int[] colors = new int[0];
    private String[] labels = new String[0];
    private String[] valueTexts = null;
    private float goal = -1f;
    private String goalText = null;

    private final Paint barPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint labelPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint valuePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint goalPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint goalTextPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF rect = new RectF();

    public BarChartView(Context context) {
        this(context, null);
    }

    public BarChartView(Context context, AttributeSet attrs) {
        super(context, attrs);
        float sp = getResources().getDisplayMetrics().scaledDensity;
        labelPaint.setColor(Color.parseColor("#9CA3AF"));
        labelPaint.setTextSize(10 * sp);
        labelPaint.setTextAlign(Paint.Align.CENTER);
        valuePaint.setColor(Color.parseColor("#374151"));
        valuePaint.setTextSize(10 * sp);
        valuePaint.setTextAlign(Paint.Align.CENTER);
        valuePaint.setFakeBoldText(true);
        goalPaint.setColor(Color.parseColor("#F59E0B"));
        goalPaint.setStyle(Paint.Style.STROKE);
        goalPaint.setStrokeWidth(2 * getResources().getDisplayMetrics().density);
        goalPaint.setPathEffect(new DashPathEffect(new float[]{12f, 8f}, 0f));
        goalTextPaint.setColor(Color.parseColor("#B45309"));
        goalTextPaint.setTextSize(10 * sp);
        goalTextPaint.setTextAlign(Paint.Align.RIGHT);
    }

    /**
     * @param values     막대 값
     * @param colors     막대 색 (values 와 같은 길이)
     * @param labels     막대 아래 라벨 (빈 문자열이면 생략)
     * @param valueTexts 막대 위 텍스트 (null 이면 생략)
     * @param goal       목표선 값 (음수면 그리지 않음)
     * @param goalText   목표선 라벨
     */
    public void setData(float[] values, int[] colors, String[] labels, String[] valueTexts,
                        float goal, String goalText) {
        this.values = values;
        this.colors = colors;
        this.labels = labels;
        this.valueTexts = valueTexts;
        this.goal = goal;
        this.goalText = goalText;
        invalidate();
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        int n = values.length;
        if (n == 0) return;

        float density = getResources().getDisplayMetrics().density;
        float labelH = labelPaint.getTextSize() + 6 * density;
        float valueH = valueTexts != null ? valuePaint.getTextSize() + 4 * density : 4 * density;
        float top = getPaddingTop() + valueH;
        float bottom = getHeight() - getPaddingBottom() - labelH;
        float left = getPaddingLeft();
        float width = getWidth() - getPaddingLeft() - getPaddingRight();
        float chartH = Math.max(1f, bottom - top);

        float max = Math.max(goal, 1f);
        for (float v : values) max = Math.max(max, v);

        float slot = width / n;
        float barW = Math.max(2f, slot * (n > 12 ? 0.7f : 0.55f));
        float radius = Math.min(barW / 2, 6 * density);

        for (int i = 0; i < n; i++) {
            float cx = left + slot * i + slot / 2;
            float h = values[i] <= 0 ? 2 * density : chartH * values[i] / max;
            rect.set(cx - barW / 2, bottom - h, cx + barW / 2, bottom);
            barPaint.setColor(colors[i]);
            canvas.drawRoundRect(rect, radius, radius, barPaint);
            // 아래쪽 모서리는 각지게
            canvas.drawRect(rect.left, Math.max(rect.top, bottom - radius), rect.right, bottom, barPaint);

            if (valueTexts != null && valueTexts[i] != null && !valueTexts[i].isEmpty()) {
                canvas.drawText(valueTexts[i], cx, bottom - h - 4 * density, valuePaint);
            }
            if (labels != null && i < labels.length && labels[i] != null && !labels[i].isEmpty()) {
                canvas.drawText(labels[i], cx, bottom + labelH - 4 * density, labelPaint);
            }
        }

        if (goal > 0) {
            float y = bottom - chartH * goal / max;
            canvas.drawLine(left, y, left + width, y, goalPaint);
            if (goalText != null) canvas.drawText(goalText, left + width, y - 4 * density, goalTextPaint);
        }
    }
}
