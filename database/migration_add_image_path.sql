-- Migration: Add image_path column to symbols table
-- Run this if your database already exists and doesn't have the image_path column

ALTER TABLE symbols 
ADD COLUMN IF NOT EXISTS image_path VARCHAR(500);

