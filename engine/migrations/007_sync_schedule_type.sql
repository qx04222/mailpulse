-- 推送计划增加 sync_only 类型
ALTER TABLE digest_schedules DROP CONSTRAINT IF EXISTS digest_schedules_report_type_check;
ALTER TABLE digest_schedules ADD CONSTRAINT digest_schedules_report_type_check
    CHECK (report_type IN ('brief', 'full_docx', 'full_pdf', 'brief_with_docx', 'sync_only'));
