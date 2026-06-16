-- ============================================================
-- SAUNDARYA BEAUTY CARE - SEED DATA
-- ============================================================
-- Default admin password: Admin@Saundarya2024
-- CHANGE IMMEDIATELY after first login!
-- Hash generated with bcrypt rounds=12

INSERT INTO users (username,email,full_name,hashed_pw,role)
VALUES (
  'admin',
  'admin@saundarya.com',
  'Saundarya Beautycare',
  '$2b$12$b8lmKZyPV/OFGpOdAUX4ge/Wz1cYjbmmSL0MQZKFo1RW36B02nviq',
  'admin'
);

-- ============================================================
-- SYSTEM CONFIG
-- ============================================================
INSERT INTO system_config VALUES ('salon_name',    'Saundarya Beauty Care & Academy', 1, SYSTIMESTAMP);
INSERT INTO system_config VALUES ('salon_phone1',  '96621 35422',  1, SYSTIMESTAMP);
INSERT INTO system_config VALUES ('salon_phone2',  '9723044589',   1, SYSTIMESTAMP);
INSERT INTO system_config VALUES ('salon_address', '12, Vishnuprashad Society, Outside Panigate, Waghodiya Road, Vadodara', 1, SYSTIMESTAMP);
INSERT INTO system_config VALUES ('wa_api_url',    '', 1, SYSTIMESTAMP);
INSERT INTO system_config VALUES ('wa_api_token',  '', 1, SYSTIMESTAMP);
INSERT INTO system_config VALUES ('wa_instance_id','', 1, SYSTIMESTAMP);
INSERT INTO system_config VALUES ('pw_att',        'ATT123', 1, SYSTIMESTAMP);
INSERT INTO system_config VALUES ('inv_prefix',    'INV', 1, SYSTIMESTAMP);
INSERT INTO system_config VALUES ('br_prefix',     'BR',  1, SYSTIMESTAMP);

-- ============================================================
-- SERVICE CATALOG
-- ============================================================
-- HAIRCUT
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('haircut','One Length Haircut',150,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('haircut','Basic Haircut',250,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('haircut','Advance Haircut',500,3);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('haircut','Butterfly Haircut',650,4);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('haircut','Stepcut Layers Cut',350,5);
-- HAIR WASH
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairwash','Basic Hairwash',250,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairwash','Only Shampoo',150,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairwash','Shampoo & Mask',350,3);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairwash','Dip Mask & Shampoo',500,4);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairwash','Advance Hair Wash',500,5);
-- HAIR SPA
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairspa','Herbal Spa',1000,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairspa','Hair Treatment Spa',1850,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairspa','Smoothing Spa',1500,3);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairspa','Protein Spa',2000,4);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairspa','Bon Therapin Spa',2500,5);
-- HAIR TREATMENT
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairtreatment','Keratin',3500,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairtreatment','Elastine',4500,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairtreatment','Bottox',5500,3);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairtreatment','Nanoplastia',7000,4);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairtreatment','Bontherapi',5500,5);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairtreatment','Smoothening',5000,6);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairtreatment','Rebonding',3500,7);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairtreatment','Straightening',4500,8);
-- HAIR COLOUR
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('haircolour','Root Touchup',1500,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('haircolour','Basic Global Haircolor',2500,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('haircolour','Fashion Sade Hair Color',3500,3);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('haircolour','Global Highlight',3500,4);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('haircolour','Baliaz',2500,5);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('haircolour','Ombrey',3000,6);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('haircolour','Basic Highlight',1850,7);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('haircolour','Highlight with Haircolour',5500,8);
-- HAIR STYLING
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairstyling','Blow Dryer',250,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairstyling','Advance Blow Dryer',350,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairstyling','Ironing / Straightening',500,3);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairstyling','Curls',650,4);
-- HAIR SCALP
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairscalp','Oily Scalp Treatment',1000,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairscalp','Dandruff Treatment',1500,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairscalp','Hairfall Treatment',1850,3);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairscalp','Sensitive Scalp Treatment',1500,4);
-- THREADING
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('threading','Eyebrow Threading',50,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('threading','Upper Lips Threading',20,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('threading','Chin Threading',20,3);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('threading','Eyebrow + Forehead + Upper Lips',70,4);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('threading','Eyebrow + Forehead + Upper Lips + Chin',90,5);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('threading','Full Face Threading',200,6);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('threading','Sideblok',100,7);
-- WAXING
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('waxing','Underarms Herbal Wax',50,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('waxing','Underarms Cream Wax',100,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('waxing','Full Hand Herbal Wax',150,3);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('waxing','Full Hand Cream Wax',250,4);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('waxing','Full Hand Lipo Wax',350,5);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('waxing','Half Leg Herbal Wax',150,6);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('waxing','Half Leg Cream Wax',250,7);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('waxing','Full Leg Herbal Wax',300,8);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('waxing','Full Leg Cream Wax',500,9);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('waxing','Full Body Herbal Wax',1000,10);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('waxing','Full Body Cream Wax',2000,11);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('waxing','Brazilian Wax',1350,12);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('waxing','Bikini Wax Herbal',550,13);
-- FACIAL
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('facial','Herbal Facial',750,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('facial','Fruit Facial',750,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('facial','Green Apple Facial',1000,3);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('facial','Gold Facial',1000,4);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('facial','Diamond Facial',1000,5);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('facial','Silver Facial',1500,6);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('facial','D-Tan Facial',1500,7);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('facial','Whitening Facial',1500,8);
-- CLEANUP
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('cleanup','Herbal Clinup',550,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('cleanup','Fruit Clinup',550,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('cleanup','Gold Clinup',550,3);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('cleanup','Diamond Clinup',550,4);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('cleanup','Silver Clinup',1000,5);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('cleanup','D-Tan Clinup',1000,6);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('cleanup','Whitening Clinup',1000,7);
-- O3 FACIAL
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('o3facial','Basic O3 + Clinup',1500,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('o3facial','Advance O3 + Clinup',2000,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('o3facial','O3 + Basic Facial',1850,3);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('o3facial','O3 + Whitening Facial',2500,4);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('o3facial','O3 + Diamond Facial',3000,5);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('o3facial','O3 + Zeel Peel Facial',4500,6);
-- HYDRA FACIAL
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hydrafacial','Basic Hydra Facial',2500,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hydrafacial','Advance Hydra Facial',4000,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hydrafacial','Treatment Hydra Facial',4500,3);
-- MANICURE
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('manicure','Hand Manicure Herbal',750,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('manicure','Hand Manicure Shiner',1000,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('manicure','Hand Manicure Whitening',1500,3);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('manicure','Hand Manicure D-Tan',1200,4);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('manicure','Hand Manicure Polishing',2000,5);
-- PEDICURE
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('pedicure','Leg Pedicure Herbal',750,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('pedicure','Leg Pedicure Shiner',1000,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('pedicure','Leg Pedicure Whitening',1500,3);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('pedicure','Leg Pedicure D-Tan',1200,4);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('pedicure','Leg Pedicure Polishing',2000,5);
-- POLISHING
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('polishing','Hand Shiner',1000,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('polishing','Full Leg Shiner',1100,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('polishing','Full Body Shiner',4500,3);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('polishing','Face Shiner',500,4);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('polishing','Full Body Skin Polishing',5500,5);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('polishing','Full Body D-Tan',3000,6);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('polishing','Face D-Tan',750,7);
-- MAKEUP
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('makeup','Party Makeup',1200,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('makeup','HD Makeup',2500,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('makeup','Airbrush Makeup',3500,3);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('makeup','Engagement Makeup',3000,4);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('makeup','Reception Makeup',3500,5);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('makeup','Sangeet Makeup',2000,6);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('makeup','Haldi Makeup',1500,7);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('makeup','Mehendi Makeup',1500,8);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('makeup','Saree Draping',500,9);
-- HAIRSTYLE
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairstyle','Bridal Hair Set',2000,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairstyle','Party Hair Set',1000,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairstyle','Reception Hair Set',1500,3);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('hairstyle','Sangeet Hair Set',1200,4);
-- BRIDAL MAKEUP
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('bridalmakeup','Bridal HD Makeup',20999,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('bridalmakeup','Bridal Airbrush Makeup',25999,2);
-- SIDER MAKEUP
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('sidermakeup','Basic Makeup + Hair',2299,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('sidermakeup','Basic + Lashes',3999,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('sidermakeup','Basic + Extension',5999,3);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('sidermakeup','Premium + Lens',7999,4);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('sidermakeup','HD Makeup Engagement/Reception',12500,5);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('sidermakeup','UHD Makeup',15499,6);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('sidermakeup','Airbrush + Flower',18499,7);
-- GROOM PACKAGES
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('groompkg','Basic Groom Package',3500,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('groompkg','Advance Groom Package',6000,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('groompkg','Premium Groom Package',8000,3);
-- NAILS
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('nails','Gel Polish - Two Hands',650,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('nails','Gel Polish - One Hand',350,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('nails','Feet Gel Polish',600,3);
-- NAIL ART
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('nailart','Nail Art (per finger)',50,1);
-- NAIL EXTENSION
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('nailext','Temp Extension + Gel (2H)',1100,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('nailext','Gel Extension + Gel (2H)',1999,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('nailext','Acrylic Extension + Gel (2H)',1999,3);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('nailext','Temp Extension + Gel (1H)',550,4);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('nailext','Gel Extension + Gel (1H)',1000,5);
-- NAIL REMOVAL
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('nailremoval','Gel Polish Removal',200,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('nailremoval','Temp Extension Removal',400,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('nailremoval','Gel Extension Removal',500,3);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('nailremoval','Acrylic Extension Removal',500,4);
-- FEET EXTENSION
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('feetext','Feet Gel Polish',600,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('feetext','Temp Feet Extension',1000,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('feetext','Permanent Feet Extension',1200,3);
-- PACKAGES
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('package','Final Sitting Package',40000,1);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('package','1st Sitting Package',55000,2);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('package','5-Function Package',74999,3);
INSERT INTO service_catalog (category,name,base_price,sort_order) VALUES ('package','Premium 3-Sitting Package',95000,4);

COMMIT;
