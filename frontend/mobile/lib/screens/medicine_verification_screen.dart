import 'package:flutter/material.dart';

class MedicineVerificationScreen extends StatelessWidget {
  const MedicineVerificationScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final rows = [
      {
        'field': 'Medicine',
        'prescribed': 'Amlodipine',
        'scanned': 'Amlodipine',
        'status': 'Match'
      },
      {
        'field': 'Strength',
        'prescribed': '5 mg',
        'scanned': '10 mg',
        'status': 'Risk'
      },
      {
        'field': 'Schedule',
        'prescribed': 'Once daily',
        'scanned': 'Twice daily',
        'status': 'Mismatch'
      },
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text('Medicine Verification'),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF1A7C6E), Color(0xFF0F584F)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(22),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Scan medication',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 24,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Quickly detect mismatches and dosage drift before treatment continues.',
                    style: TextStyle(
                      color: Colors.white70,
                      fontSize: 14,
                    ),
                  ),
                  const SizedBox(height: 18),
                  Row(
                    children: [
                      Expanded(
                        child: ElevatedButton.icon(
                          onPressed: () {},
                          icon: const Icon(Icons.camera_alt_rounded),
                          label: const Text('Camera'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () {},
                          icon: const Icon(Icons.upload_file_rounded),
                          label: const Text('Upload'),
                          style: ButtonStyle(
                            foregroundColor:
                                WidgetStatePropertyAll(Colors.white),
                            side: WidgetStatePropertyAll(
                                const BorderSide(color: Colors.white54)),
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            const Text(
              'Medication review',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w800,
                color: Color(0xFF133230),
              ),
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(18),
              ),
              child: Column(
                children: rows.map((item) {
                  final status = item['status'] as String;
                  final color = status == 'Match'
                      ? Colors.green
                      : status == 'Risk'
                          ? Colors.orange
                          : Colors.red;

                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          flex: 2,
                          child: Text(
                            item['field'] as String,
                            style: const TextStyle(
                              fontWeight: FontWeight.w600,
                              color: Color(0xFF1E3A36),
                            ),
                          ),
                        ),
                        Expanded(
                          flex: 2,
                          child: Text(item['prescribed'] as String),
                        ),
                        Expanded(
                          flex: 2,
                          child: Text(item['scanned'] as String),
                        ),
                        Expanded(
                          child: Container(
                            padding: const EdgeInsets.symmetric(
                                vertical: 6, horizontal: 8),
                            decoration: BoxDecoration(
                              color: color.withValues(alpha: 0.13),
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: Text(
                              status,
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                color: color,
                                fontWeight: FontWeight.w700,
                                fontSize: 11,
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  );
                }).toList(),
              ),
            ),
            const SizedBox(height: 20),
            const Text(
              'AI summary',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w800,
                color: Color(0xFF133230),
              ),
            ),
            const SizedBox(height: 12),
            ...[
              'Detected 10 mg; prescribed strength is 5 mg.',
              'Label instructions say twice daily, while the prescription says once daily.',
              'Medicine name matches the prescription and patient record.',
            ].map(
              (item) => Container(
                margin: const EdgeInsets.only(bottom: 10),
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: 26,
                      height: 26,
                      decoration: BoxDecoration(
                        color: const Color(0xFFEB9C48).withValues(alpha: 0.16),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Icon(
                        Icons.priority_high_rounded,
                        size: 14,
                        color: Color(0xFFB96C2E),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(item),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
