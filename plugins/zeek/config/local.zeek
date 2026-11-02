# Configuration Zeek locale
@load protocols/conn/known-hosts
@load protocols/conn/known-services
@load protocols/ssl/validate-certs
@load protocols/http/detect-webapps
@load policy/tuning/json-logs.zeek

redef LogAscii::use_json = T;
