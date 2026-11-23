/* Pasangan DO kedua sementara untuk tiket sebelum proses pisah.
   Tabel ini bukan penyimpanan tiket atau berat lokal. */
SET NOCOUNT ON;
USE [Main];
GO

IF OBJECT_ID('dbo.TiketRencanaPemisahan', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.TiketRencanaPemisahan (
        TicketID   INT           NOT NULL PRIMARY KEY,
        TicketNo   VARCHAR(50)   NOT NULL,
        NoDO2      VARCHAR(50)   NOT NULL,
        CreatedAt  DATETIME2(0)  NOT NULL
            CONSTRAINT DF_TiketRencanaPemisahan_CreatedAt DEFAULT (SYSDATETIME()),
        CreatedBy  INT           NULL,
        CONSTRAINT CK_TiketRencanaPemisahan_NoDO2
            CHECK (LEN(LTRIM(RTRIM(NoDO2))) > 0)
    );
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM dbo.SchemaLog
    WHERE Script = 'database/perubahan/024_tiket_pisah_plan.sql'
)
    INSERT INTO dbo.SchemaLog (Script, App)
    VALUES ('database/perubahan/024_tiket_pisah_plan.sql', 'CPOS');
GO