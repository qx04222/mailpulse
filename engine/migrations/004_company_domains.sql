-- 公司增加邮箱域名字段
ALTER TABLE companies ADD COLUMN IF NOT EXISTS email_domains text[] DEFAULT '{}';

-- 人员增加自动发现标记
ALTER TABLE people ADD COLUMN IF NOT EXISTS auto_discovered boolean DEFAULT false;

-- 填入已知域名
UPDATE companies SET email_domains = ARRAY['arcview.ca'] WHERE name = 'Arcview';
UPDATE companies SET email_domains = ARRAY['arcpath.ca'] WHERE name = 'Arcpath';
UPDATE companies SET email_domains = ARRAY['terrax.ca'] WHERE name = 'Terrax';
UPDATE companies SET email_domains = ARRAY['arctrek.ca'] WHERE name = 'Arctrek';
UPDATE companies SET email_domains = ARRAY['torquemax.ca'] WHERE name = 'TorqueMax';
UPDATE companies SET email_domains = ARRAY['arcnexus.ca'] WHERE name = 'ArcNexus';
