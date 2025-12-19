package com.studylens.client.model;

import com.google.gson.annotations.SerializedName;

public class StudyImage {
    public int id;

    @SerializedName("image_url")
    public String imageUrl;

    @SerializedName("created_at")
    public String createdAt;
}

