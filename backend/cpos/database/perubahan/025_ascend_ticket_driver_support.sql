/*
    Migrasi 025: relasi supir CPOS dengan tiket Ascend.
    Tabel ini BUKAN tabel tiket lokal dan tidak menyimpan master Supplier/Produk.
    TicketID/TicketNo adalah referensi ke tiket yang tetap berada di database Ascend.
*/
IF OBJECT_ID(N'dbo.AscendTicketDriver', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.AscendTicketDriver (
        TicketID           BIGINT NOT NULL,
        TicketNo           VARCHAR(50) NOT NULL,
        TicketType         VARCHAR(20) NOT NULL,
        VehicleNo          VARCHAR(50) NOT NULL,
        DriverID           BIGINT NOT NULL,
        DriverNameSnapshot NVARCHAR(100) NOT NULL,
        CreateBy           BIGINT NOT NULL,
        CreateDate         DATETIME NOT NULL CONSTRAINT DF_AscendTicketDriver_CreateDate DEFAULT (GETDATE()),
        CONSTRAINT PK_AscendTicketDriver PRIMARY KEY (TicketID),
        CONSTRAINT UX_AscendTicketDriver_TicketNo UNIQUE (TicketNo),
        CONSTRAINT CK_AscendTicketDriver_Type CHECK (TicketType IN ('Produk', 'TBSLuar')),
        CONSTRAINT FK_AscendTicketDriver_Driver FOREIGN KEY (DriverID) REFERENCES dbo.Users (UserID),
        CONSTRAINT FK_AscendTicketDriver_CreateBy FOREIGN KEY (CreateBy) REFERENCES dbo.Users (UserID)
    );

    CREATE INDEX IX_AscendTicketDriver_DriverDate
        ON dbo.AscendTicketDriver (DriverID, CreateDate DESC)
        INCLUDE (TicketNo, VehicleNo, TicketType);
END
GO
