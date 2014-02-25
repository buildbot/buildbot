DELIMITER $$

CREATE PROCEDURE  CleanBuildRequets()
BEGIN
	START TRANSACTION;
	CREATE TABLE BUILDREQUESTS_SELECTION (id int(11) NOT NULL AUTO_INCREMENT, PRIMARY KEY (id)) ENGINE=InnoDB;
	CREATE TABLE BUILDSETS_SELECTION (id int(11) NOT NULL AUTO_INCREMENT, PRIMARY KEY (id)) ENGINE=InnoDB;


	insert into BUILDREQUESTS_SELECTION
	(select id from buildrequests
		where complete = 1 and complete_at is not null and
				FROM_UNIXTIME(complete_at) < timestampadd(day, -30, CURDATE()) LIMIT 100000);


	insert into BUILDSETS_SELECTION
	(select distinct br.buildsetid from buildrequests br
		join  BUILDREQUESTS_SELECTION brs on br.id = brs.id);

	-- delete sourcestampsets rows
	-- this cascades delete to sourcestamps table
	DELETE from sourcestampsets where exists
		(select distinct sourcestampsetid from buildsets inner join BUILDSETS_SELECTION
			on buildsets.id = BUILDSETS_SELECTION.id
			 where sourcestampsets.id = buildsets.sourcestampsetid) LIMIT 100000;

	-- delete buildsets rows
	-- this cascades delete to buildset_properties
	DELETE from buildsets where exists
		(select id from BUILDSETS_SELECTION where BUILDSETS_SELECTION.id = buildsets.id) LIMIT 100000;

	-- delete buildrequests rows
	-- this cascades delete to builds, buildrequest_claims tables
	DELETE from buildrequests where exists
		(select id from BUILDREQUESTS_SELECTION where BUILDREQUESTS_SELECTION.id = buildrequests.id) LIMIT 100000;

	DROP TABLE BUILDREQUESTS_SELECTION;
	DROP TABLE BUILDSETS_SELECTION;
	COMMIT;
END;
