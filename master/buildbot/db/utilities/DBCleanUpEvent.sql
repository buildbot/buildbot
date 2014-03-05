CREATE EVENT DBCleanUPEvent
    ON SCHEDULE EVERY 1 WEEK
    DO
      Call CleanBuildRequets();