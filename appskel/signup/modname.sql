drop database if exists dummy;
create database dummy;
grant all privileges on dummy.* to 'foo'@'localhost' identified by 'bar';
use dummy;

create table users (
  id integer not null auto_increment,
  user_email varchar(50) not null,
  user_passwd varchar(40) not null,
  user_full_name varchar(80) null,
  user_is_active boolean not null,
  primary key(id)
);
