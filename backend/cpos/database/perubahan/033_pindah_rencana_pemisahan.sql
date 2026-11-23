SET NOCOUNT ON;
SET XACT_ABORT ON;
USE [Main];

IF OBJECT_ID('dbo.AscendTicketSplitPlan', 'U') IS NULL
    THROW 51001, 'Tabel sumber AscendTicketSplitPlan tidak ditemukan.', 1;

IF OBJECT_ID('dbo.TiketRencanaPemisahan', 'U') IS NULL
    THROW 51002, 'Tabel tujuan TiketRencanaPemisahan tidak ditemukan.', 1;

IF EXISTS (
    SELECT 1
    FROM dbo.AscendTicketSplitPlan
    WHERE PendingStatus IS NOT NULL
      AND UPPER(LTRIM(RTRIM(PendingStatus))) NOT IN (
          'MENUNGGU_DO2',
          'SELESAI_SPLIT',
          'SELESAI_TANPA_SPLIT',
          'SELESAI_PISAH',
          'SELESAI_TANPA_PISAH'
      )
)
    THROW 51003, 'Ada PendingStatus lama yang belum memiliki pemetaan. Data belum dipindahkan.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    INSERT INTO dbo.TiketRencanaPemisahan (
        TicketID,
        TicketNo,
        NoDO2,
        CreatedAt,
        CreatedBy,
        PendingFinalScaleKg,
        PendingFinalAt,
        PendingFinalBy,
        PendingStatus,
        PendingAttempts,
        PendingLastError,
        PendingCompletedAt
    )
    SELECT
        s.TicketID,
        s.TicketNo,
        NULLIF(LTRIM(RTRIM(s.NoDO2)), ''),
        s.CreatedAt,
        s.CreatedBy,
        s.PendingFinalScaleKg,
        s.PendingFinalAt,
        s.PendingFinalBy,
        CASE UPPER(LTRIM(RTRIM(s.PendingStatus)))
            WHEN 'SELESAI_SPLIT' THEN 'SELESAI_PISAH'
            WHEN 'SELESAI_TANPA_SPLIT' THEN 'SELESAI_TANPA_PISAH'
            ELSE s.PendingStatus
        END,
        s.PendingAttempts,
        s.PendingLastError,
        s.PendingCompletedAt
    FROM dbo.AscendTicketSplitPlan s
    WHERE NOT EXISTS (
        SELECT 1
        FROM dbo.TiketRencanaPemisahan t
        WHERE t.TicketID = s.TicketID
    );

    IF NOT EXISTS (
        SELECT 1
        FROM dbo.SchemaLog
        WHERE Script = 'database/perubahan/033_pindah_rencana_pemisahan.sql'
    )
    BEGIN
        INSERT INTO dbo.SchemaLog (Script, App)
        VALUES ('database/perubahan/033_pindah_rencana_pemisahan.sql', 'CPOS');
    END;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;

SELECT 'AscendTicketSplitPlan' AS NamaTabel, COUNT(*) AS JumlahBaris
FROM dbo.AscendTicketSplitPlan
UNION ALL
SELECT 'TiketRencanaPemisahan', COUNT(*)
FROM dbo.TiketRencanaPemisahan;

SELECT
    s.TicketID,
    s.TicketNo,
    s.PendingStatus AS StatusLama,
    t.PendingStatus AS StatusBaru,
    s.NoDO2 AS DOLama,
    t.NoDO2 AS DOBaru
FROM dbo.AscendTicketSplitPlan s
LEFT JOIN dbo.TiketRencanaPemisahan t ON t.TicketID = s.TicketID
ORDER BY s.TicketID;