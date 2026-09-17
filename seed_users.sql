-- Generate hashes with: python make_hash.py
-- Replace the four placeholders before running this file in Supabase SQL Editor.
insert into public.users(username,password_hash,role,examination_centre,active)
values
('setter01','PASTE_SETTER_HASH_HERE','SETTER',null,true),
('moderator01','PASTE_MODERATOR_HASH_HERE','MODERATOR',null,true),
('release01','PASTE_RELEASE_HASH_HERE','RELEASE_OFFICER',null,true),
('admin01','PASTE_ADMIN_HASH_HERE','ADMIN',null,true),
('examcentre01','PASTE_EXAM_CENTRE_HASH_HERE','EXAM_CENTRE','Main Examination Centre',true)
on conflict (username) do nothing;
