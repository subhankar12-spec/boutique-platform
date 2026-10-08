# Backup Restore

From boutique-platform, run scripts/backup-local.sh /secure/path/orders.dump and scripts/restore-drill.sh /secure/path/orders.dump. The drill restores to boutique_restore_drill and preserves the live database. Record backup-time order count and compare after restore. Encrypt backups outside the lab, limit reads and define retention. For AWS restore RDS to a new instance, validate schema/orders, measure recovery time/data loss, then review any cutover separately.
