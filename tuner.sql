CREATE TABLE shows (
	`show_id` VARCHAR(255) PRIMARY KEY, 
	`name` VARCHAR(255), 
	`url` VARCHAR(255), 
	`path` VARCHAR(255), 
	`status` VARCHAR(255), 
	`download` INT
);


CREATE TABLE episodes (
	`episode_id` VARCHAR(255) PRIMARY KEY, 
	`show_id` VARCHAR(255),
	`number` VARCHAR(255), 
	`season` VARCHAR(255), 
	`magnet` VARCHAR(255), 
	`downloaded` INT
);

