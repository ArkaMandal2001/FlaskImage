CREATE TABLE MetaData (
    DataID int NOT NULL GENERATED ALWAYS AS IDENTITY,
    imageOriginalName varchar(255) NOT NULL,
	imageUploadName varchar(255) NOT NULL,
    uploadDate TIMESTAMP DEFAULT NOW(),
    userID int,
    PRIMARY KEY(DataID)
);