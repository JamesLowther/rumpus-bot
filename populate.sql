
drop table if exists subjects;

PRAGMA foreign_keys = ON;

create table subjects (
  id		    text,
  name		  text,
  block		  int,
  offenses  int,
  deeds     int,
  points    int,
  primary key (id)
);

--insert into subjects values
--		('1234', 'Articuler', 0, 10, 0, 0, 0);

	