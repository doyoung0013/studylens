package com.studylens.client.model;

import com.google.gson.annotations.SerializedName;

public class StudyImage {
    public int id;

    @SerializedName("imageUrl")  // Django 서버에서 보내는 키와 매핑
    public String imageUrl;

    @SerializedName("created_at")
    public String createdAt;
}

/* 서버응답 형태
{
  "id": 3,
  "imageUrl": "http://server/image/2023-12-12_10-21-33.jpg",
  "created_at": "2023-12-12T10:21:33"
}

 */
