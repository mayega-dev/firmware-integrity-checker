#ifndef INTEGRITY_CHECKER_H
#define INTEGRITY_CHECKER_H

#include <stdbool.h>

/**
 * @brief Initializes the runtime monitor task.
 */
void integrity_checker_init(void);

/**
 * @brief Triggers an immediate baseline calculation or explicit verification.
 * @return true if verification succeeds, false if verification fails or baseline unset.
 */
bool integrity_checker_verify_now(void);

#endif // INTEGRITY_CHECKER_H