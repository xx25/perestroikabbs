-- Migration script to add language support to existing databases
-- Run this if you have an existing Perestroika BBS database

-- Add language preference column to users table
ALTER TABLE users ADD COLUMN language_pref VARCHAR(5) DEFAULT 'en';

-- Update existing users to default language
UPDATE users SET language_pref = 'en' WHERE language_pref IS NULL;

-- Optional: Set Russian language for users with Russian encoding preferences
UPDATE users SET language_pref = 'ru'
WHERE encoding_pref IN ('windows-1251', 'koi8-r', 'cp866');