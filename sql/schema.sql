-- filepath: sql/schema.sql
CREATE DATABASE IF NOT EXISTS product_reviews
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE product_reviews;

-- 원시 리뷰 적재 테이블 (Step1)
CREATE TABLE IF NOT EXISTS reviews_raw (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    review_id     VARCHAR(64) NOT NULL,
    review_date   DATETIME NOT NULL,
    product_id    VARCHAR(64) NOT NULL,
    product_name  VARCHAR(255) NOT NULL,
    user_id       VARCHAR(64) NULL,
    channel       VARCHAR(64) NULL,
    rating        TINYINT NULL,
    review_text   TEXT NOT NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY ux_review_unique (review_id, product_id)
);

-- 일자·상품별 Data Mart (Step2에서 재빌드)
CREATE TABLE IF NOT EXISTS dm_product_review_daily (
    id                BIGINT AUTO_INCREMENT PRIMARY KEY,
    review_date       DATE NOT NULL,
    product_id        VARCHAR(64) NOT NULL,
    product_name      VARCHAR(255) NOT NULL,
    channel           VARCHAR(64) NULL,
    review_count      INT NOT NULL,
    avg_rating        DECIMAL(3,2) NULL,
    positive_ratio    DECIMAL(5,4) NULL,
    negative_ratio    DECIMAL(5,4) NULL,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY ux_dm_daily (review_date, product_id, channel)
);

-- 상품 레벨 요약 Mart (Step3에서 재빌드)
CREATE TABLE IF NOT EXISTS dm_product_review_summary (
    id                BIGINT AUTO_INCREMENT PRIMARY KEY,
    product_id        VARCHAR(64) NOT NULL,
    product_name      VARCHAR(255) NOT NULL,
    channel           VARCHAR(64) NULL,
    total_reviews     INT NOT NULL,
    avg_rating        DECIMAL(3,2) NULL,
    positive_ratio    DECIMAL(5,4) NULL,
    negative_ratio    DECIMAL(5,4) NULL,
    last_review_date  DATE NULL,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY ux_dm_summary (product_id, channel)
);
