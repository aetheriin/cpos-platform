/* Pasangan DO kedua sementara untuk tiket Ascend sebelum proses split.
   Tabel ini bukan penyimpanan tiket atau berat lokal. */
SET NOCOUNT ON;
USE [Main];
GO

IF OBJECT_ID('dbo.AscendTicketSplitPlan', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.AscendTicketSplitPlan (
        TicketID   INT           NOT NULL PRIMARY KEY,
        TicketNo   VARCHAR(50)   NOT NULL,
        NoDO2      VARCHAR(50)   NOT NULL,
        CreatedAt  DATETIME2(0)  NOT NULL
            CONSTRAINT DF_AscendTicketSplitPlan_CreatedAt DEFAULT (SYSDATETIME()),
        CreatedBy  INT           NULL,
        CONSTRAINT CK_AscendTicketSplitPlan_NoDO2
            CHECK (LEN(LTRIM(RTRIM(NoDO2))) > 0)
    );
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM dbo.SchemaLog
    WHERE Script = 'database/perubahan/024_ascend_ticket_split_plan.sql'
)
    INSERT INTO dbo.SchemaLog (Script, App)
    VALUES ('database/perubahan/024_ascend_ticket_split_plan.sql', 'CPOS');
GO