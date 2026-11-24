package com.studylens.client.model;

import com.google.gson.annotations.SerializedName;

public class StudyImage {
    public long id;

    /** 일정 시간만 유효한 서명된 이미지 URL */
    @SerializedName("image_url")
    public String imageUrl;

    @SerializedName("captured_at")
    public String capturedAt;

    @SerializedName("created_at")
    public String createdAt;
}
