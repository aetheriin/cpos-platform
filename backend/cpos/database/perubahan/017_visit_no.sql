/* Nomor tiket kunjungan (mis. HO/2026-11/0125): kolom VisitNo di FaceActivity + penghitung per area per bulan. Aman dijalankan ulang. */
SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;
IF OBJECT_ID('dbo.VisitCounter') IS NULL
CREATE TABLE dbo.VisitCounter (
    CompAreaID BIGINT  NOT NULL CONSTRAINT FK_VisitCounter_Area REFERENCES dbo.CompanyArea (CompAreaID),
    Periode    CHAR(7) NOT NULL,   -- yyyy-MM
    LastNo     INT     NOT NULL CONSTRAINT DF_VisitCounter_Last DEFAULT (0),
    CONSTRAINT PK_VisitCounter PRIMARY KEY (CompAreaID, Periode)
);
GO
IF COL_LENGTH('dbo.FaceActivity', 'VisitNo') IS NULL
    ALTER TABLE dbo.FaceActivity ADD VisitNo VARCHAR(30) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_FaceAct_VisitNo' AND object_id = OBJECT_ID('dbo.FaceActivity'))
    CREATE UNIQUE INDEX UX_FaceAct_VisitNo ON dbo.FaceActivity (VisitNo) WHERE VisitNo IS NOT NULL;
GO
IF NOT EXISTS (SELECT 1 FROM dbo.SchemaLog WHERE Script = 'database/perubahan/017_visit_no.sql')
    INSERT INTO dbo.SchemaLog (Script, App) VALUES ('database/perubahan/017_visit_no.sql', 'CPOS');
GO